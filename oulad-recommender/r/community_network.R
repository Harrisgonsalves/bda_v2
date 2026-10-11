# Community detection over students, based on the courses/resources recommended to them.
# Usage (called by the worker): Rscript community_network.R <mongo_uri> <db> <module> <presentation> <max_students> <outdir>
# One-time install:  install.packages(c("mongolite","igraph","visNetwork","htmlwidgets","jsonlite"))
suppressPackageStartupMessages({
  library(mongolite); library(igraph); library(visNetwork); library(htmlwidgets); library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
uri <- args[1]; dbname <- args[2]; module <- args[3]; pres <- args[4]
max_n <- as.integer(args[5]); outdir <- args[6]
dir.create(outdir, showWarnings = FALSE, recursive = TRUE)
set.seed(42)

ver <- mongo("model_metadata", db = dbname, url = uri)$find('{"is_active": true}', fields = '{"version":1,"_id":0}')$version
if (length(ver) == 0) stop("No active model. Run the recommendation rebuild first.")

q <- toJSON(list(code_module = module, code_presentation = pres, model_version = ver), auto_unbox = TRUE)
df <- mongo("recommendations", db = dbname, url = uri)$find(q, fields = '{"student_id":1,"resource_id":1,"_id":0}')
if (nrow(df) == 0) stop("No recommendations stored for this course presentation.")

# Keep the graph small enough to read: a random subset of students
ids <- unique(df$student_id)
ids <- sample(ids, min(length(ids), max_n))
df <- df[df$student_id %in% ids, ]

# Student x resource incidence matrix; shared[i,j] = number of recommended resources two students have in common
M <- unclass(table(df$student_id, df$resource_id)); M[M > 0] <- 1
shared <- M %*% t(M); diag(shared) <- 0
vals <- shared[upper.tri(shared)]
if (sum(vals > 0) == 0) stop("Students share no recommendations; nothing to connect.")
thr <- max(1, ceiling(quantile(vals[vals > 0], 0.5)))   # keep the stronger half of the links
adj <- shared * (shared >= thr)

g <- graph_from_adjacency_matrix(adj, mode = "undirected", weighted = TRUE, diag = FALSE)
g <- delete_vertices(g, which(degree(g) == 0))
if (vcount(g) < 3) stop("Too few connected students. Try more students.")

# Edge betweenness treats weights as distances, so strong links get a short distance
comm <- cluster_edge_betweenness(g, weights = 1 / E(g)$weight)
memb <- membership(comm)

# Static plot (dark background)
png(file.path(outdir, "community.png"), width = 1100, height = 850, res = 130, bg = "#0E1320")
par(bg = "#0E1320")
plot(comm, g, vertex.size = 5, vertex.label = NA, edge.color = "#46506f",
     main = "Community Detection - Edge Betweenness", col.main = "#E6EAF5")
dev.off()

# Interactive version
nodes <- data.frame(id = V(g)$name, label = V(g)$name, group = paste("Community", memb[V(g)$name]),
                    title = paste0("Student ", V(g)$name, "<br>Community ", memb[V(g)$name],
                                   "<br>Links: ", degree(g)), stringsAsFactors = FALSE)
el <- as_data_frame(g, what = "edges")
edges <- data.frame(from = el$from, to = el$to, value = el$weight,
                    title = paste(el$weight, "shared recommendations"))
w <- visNetwork(nodes, edges, width = "100%", height = "100%", background = "#0E1320") |>
  visNodes(shape = "dot", size = 12, font = list(color = "#E6EAF5")) |>
  visEdges(color = list(color = "#46506f", highlight = "#8EA2FF"), smooth = FALSE) |>
  visOptions(highlightNearest = list(enabled = TRUE, degree = 1), selectedBy = "group") |>
  visInteraction(hover = TRUE, navigationButtons = TRUE) |>
  visPhysics(stabilization = list(iterations = 150))
saveWidget(w, file.path(outdir, "network.html"), selfcontained = FALSE, libdir = "lib")

# Summary for the dashboard
summ <- lapply(sort(unique(as.integer(memb))), function(k) {
  members <- as.integer(names(memb)[memb == k])
  top <- sort(table(df$resource_id[df$student_id %in% members]), decreasing = TRUE)
  list(community = k, size = length(members), top_resources = as.integer(names(top)[seq_len(min(3, length(top)))]))
})
write_json(list(generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"), code_module = module,
                code_presentation = pres, model_version = ver, students = vcount(g), links = ecount(g),
                communities = length(comm), modularity = round(modularity(comm), 3), min_shared = thr,
                groups = summ), file.path(outdir, "communities.json"), auto_unbox = TRUE, pretty = TRUE)
cat("Network analysis finished\n")
