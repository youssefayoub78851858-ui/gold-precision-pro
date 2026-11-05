
const http = require("http");

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.setHeader("Content-Type", "application/json; charset=utf-8");

  if (req.url === "/health" && req.method === "GET") {
    res.writeHead(200);
    return res.end(JSON.stringify({
      system: "Gold Precision Pro AI",
      status: "online",
      marketData: "not_connected",
      trading: "disabled"
    }));
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running on port ${PORT}`);
});
