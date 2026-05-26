# Reproduce Figure 1: emissions per capita vs. GDP per capita PPP.
# Run from the root of the emissionKuznets_worldbank folder:
#   Rscript replicate_figure1.R
# or:
#   Rscript replicate_figure1.R /path/to/emissionKuznets_worldbank

args <- commandArgs(trailingOnly = TRUE)
base_dir <- if (length(args) >= 1) args[1] else getwd()

YEAR <- "2018"
AMAZON_GDP_PC_PPP_2018 <- 9968.0
AMAZON_EMISSIONS_PC_2018 <- 40.6

one_match <- function(pattern) {
  files <- Sys.glob(pattern)
  if (length(files) == 0) stop(paste("No file matched:", pattern))
  files[1]
}

read_wdi_csv <- function(path, value_name) {
  raw <- read.csv(path, skip = 4, check.names = FALSE)
  out <- raw[, c("Country Name", "Country Code", YEAR)]
  names(out)[names(out) == YEAR] <- value_name
  out[[value_name]] <- as.numeric(out[[value_name]])
  out
}

input_dir <- file.path(base_dir, "input")
doc_dir <- file.path(base_dir, "documentation")
out_dir <- file.path(base_dir, "output", "results", "other")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

gdp_file <- one_match(file.path(input_dir, "API_NY.GDP.PCAP.PP.CD*.csv"))
co2_file <- one_match(file.path(input_dir, "API_EN.ATM.CO2E.PC*.csv"))
metadata_file <- one_match(file.path(doc_dir, "Metadata_Country_API_NY.GDP.PCAP.PP.CD*.csv"))

gdp <- read_wdi_csv(gdp_file, "gdp_pc_ppp_2018")
co2 <- read_wdi_csv(co2_file, "emissions_pc_2018")
meta <- read.csv(metadata_file, check.names = FALSE)[, c("Country Code", "Region")]

df <- merge(gdp, co2[, c("Country Code", "emissions_pc_2018")], by = "Country Code")
df <- merge(df, meta, by = "Country Code", all.x = TRUE)

is_country_or_territory <- !is.na(df$Region) & nchar(as.character(df$Region)) > 0
is_eu <- df$`Country Code` == "EUU"
df <- df[is_country_or_territory | is_eu, ]
df <- df[!is.na(df$gdp_pc_ppp_2018) & !is.na(df$emissions_pc_2018) &
           df$gdp_pc_ppp_2018 > 0 & df$emissions_pc_2018 > 0, ]
df$gdp_pc_ppp_2018_100k <- df$gdp_pc_ppp_2018 / 100000

amazon <- data.frame(
  `Country Code` = "AMAZON",
  `Country Name` = "Brazilian Amazon",
  gdp_pc_ppp_2018 = AMAZON_GDP_PC_PPP_2018,
  emissions_pc_2018 = AMAZON_EMISSIONS_PC_2018,
  Region = "Brazilian Amazon",
  gdp_pc_ppp_2018_100k = AMAZON_GDP_PC_PPP_2018 / 100000,
  check.names = FALSE
)
plot_data <- rbind(df, amazon)
write.csv(plot_data, file.path(out_dir, "figure1_source_data_R.csv"), row.names = FALSE)

plot_figure <- function(filename, device = c("png", "pdf")) {
  device <- match.arg(device)
  if (device == "png") {
    png(filename, width = 2400, height = 1800, res = 300)
  } else {
    pdf(filename, width = 8, height = 6)
  }

  par(mar = c(5, 5.2, 2, 1) + 0.1, bty = "l", mgp = c(3.4, 0.8, 0))
  plot(
    df$gdp_pc_ppp_2018_100k,
    df$emissions_pc_2018,
    log = "xy",
    pch = 16,
    cex = 0.7,
    col = "black",
    xlim = c(0.006, 1.6),
    ylim = c(0.02, 60),
    xaxt = "n",
    yaxt = "n",
    xlab = "GDP per capita PPP in 2018 (100,000 int. dollars, log scale)",
    ylab = "Emission per capita in 2018 (metric tons CO2e, log scale)",
    cex.lab = 1.45,
    cex.axis = 1.1
  )
  axis(1, at = c(0.01, 0.10, 1.00), labels = c("0.01", "0.10", "1.00"), cex.axis = 1.1)
  axis(2, at = c(0.1, 1.0, 10.0), labels = c("0.1", "1.0", "10.0"), cex.axis = 1.1)

  labels <- c(CHN = "C", IND = "I", EUU = "E", USA = "U")
  for (code in names(labels)) {
    r <- df[df$`Country Code` == code, ]
    points(r$gdp_pc_ppp_2018_100k, r$emissions_pc_2018, pch = 16, col = "red", cex = 0.8)
    text(r$gdp_pc_ppp_2018_100k * 1.035, r$emissions_pc_2018, labels = labels[[code]],
         col = "red", font = 2, cex = 1.0, adj = c(0, 0.5))
  }

  points(amazon$gdp_pc_ppp_2018_100k, amazon$emissions_pc_2018, pch = 16, col = "green", cex = 0.8)
  text(amazon$gdp_pc_ppp_2018_100k * 1.035, amazon$emissions_pc_2018, labels = "Amazon",
       col = "green", font = 2, cex = 1.0, adj = c(0, 0.5))

  dev.off()
}

plot_figure(file.path(out_dir, "figure1_replicated_R.png"), "png")
plot_figure(file.path(out_dir, "figure1_replicated_R.pdf"), "pdf")

cat("Wrote files to", out_dir, "\n")
