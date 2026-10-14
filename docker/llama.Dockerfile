FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS download
WORKDIR /downloads
ADD --checksum=sha256:1c5024dfa587a3f23ef8fc066cb2578fb43d661910d4111a8941184773c237d1 https://github.com/ggml-org/llama.cpp/releases/download/b11617/llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz /downloads/llama.tar.gz
ADD --checksum=sha256:59e7bf466cf7d307c2ef9654fc4a5ba5428a4dd1e63b60fbe1b8d8591550f54f https://github.com/ggml-org/llama.cpp/releases/download/b11617/cudart-llama-b11617-bin-ubuntu-cuda-12.8-x64.tar.gz /downloads/cudart.tar.gz
RUN mkdir /opt/llama && tar -xzf llama.tar.gz -C /opt/llama --strip-components=1 \
    && tar -xzf cudart.tar.gz -C /opt/llama --strip-components=1

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
LABEL org.opencontainers.image.source="https://github.com/ggml-org/llama.cpp" \
      org.opencontainers.image.revision="14310190cd0a0c831fe949ac8cbedd8abdc90695" \
      org.opencontainers.image.version="b11617"
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libcurl4t64 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=download /opt/llama /opt/llama
ENV LD_LIBRARY_PATH=/opt/llama NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENTRYPOINT ["/opt/llama/llama-server"]
