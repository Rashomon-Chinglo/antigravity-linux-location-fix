module.exports = {
  apps: [
    {
      name: "sing-box-ag-warp",
      script: "/usr/local/bin/sing-box",
      args: "run -c /root/Project/cloud_workspace/antigravity-warp-gid/configs/sing-box-ag-warp.json",
      cwd: "/root/Project/cloud_workspace/antigravity-warp-gid",
      autorestart: true,
      max_restarts: 20,
      min_uptime: "5s",
      time: true,
      out_file: "/root/.pm2/logs/sing-box-ag-warp-out.log",
      error_file: "/root/.pm2/logs/sing-box-ag-warp-error.log"
    }
  ]
};
