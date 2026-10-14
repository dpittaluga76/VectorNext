# Captured PDF adapter outputs

These files are actual outputs from the CPU-only Docling/Tesseract adapter over the two original PDF sources and three T06 PDF fixtures. They let the Rust ingestion/durability/search tests run offline without Python or model weights. Each artifact binds its source and processing-profile SHA-256.

The live adapter tests check extraction against source text, coordinates, table headers, and visual review. Captured artifacts are not an independent gold answer set. To capture after an intentional parser change, run the processor suite with `PDF_CAPTURE=/output/artifacts`, review the differences, and copy the five document JSON files from `tmp/pdf/artifacts/` here. Do not copy timings/resources as document artifacts. Updating captures must never regenerate the PDFs or T01 labels.
