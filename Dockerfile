# Starts the lite MCP server over stdio. Python standard library only; nothing is installed.
FROM python:3.12-slim
WORKDIR /app
COPY zero_trace_lite.py mcp_server_lite.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python3", "mcp_server_lite.py"]
