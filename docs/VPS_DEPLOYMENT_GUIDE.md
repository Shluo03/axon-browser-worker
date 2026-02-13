# VPS 矩阵部署指南

> 目标：在多个云VPS上部署AdsPower + Browser Worker，实现中央控制的浏览器自动化集群

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    中央控制层 (你的本地/主服务器)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ AXON Backend │  │   Temporal   │  │  Web Dashboard (TODO)│  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP API / WebSocket
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    VPS #1     │   │    VPS #2     │   │    VPS #N     │
│  ┌─────────┐  │   │  ┌─────────┐  │   │  ┌─────────┐  │
│  │ Browser │  │   │  │ Browser │  │   │  │ Browser │  │
│  │ Worker  │  │   │  │ Worker  │  │   │  │ Worker  │  │
│  │ :8080   │  │   │  │ :8080   │  │   │  │ :8080   │  │
│  └────┬────┘  │   │  └────┬────┘  │   │  └────┬────┘  │
│       │       │   │       │       │   │       │       │
│  ┌────▼────┐  │   │  ┌────▼────┐  │   │  ┌────▼────┐  │
│  │AdsPower │  │   │  │AdsPower │  │   │  │AdsPower │  │
│  │ :50325  │  │   │  │ :50325  │  │   │  │ :50325  │  │
│  └─────────┘  │   │  └─────────┘  │   │  └─────────┘  │
│  IP: 1.2.3.4  │   │  IP: 5.6.7.8  │   │  IP: x.x.x.x  │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## 第一阶段：VPS 选型与采购

### 推荐配置（每台VPS）

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| CPU | 2核 | 4核 | AdsPower + 浏览器需要算力 |
| 内存 | 4GB | 8GB | 每个浏览器实例约1-2GB |
| 存储 | 40GB SSD | 80GB SSD | Profile数据、截图等 |
| 系统 | Ubuntu 22.04 | Ubuntu 22.04 | 必须是带GUI的版本 |
| 网络 | 独立IP | 独立IP | 住宅IP更佳（可选） |

### 云服务商对比

| 服务商 | 4核8G价格/月 | 优势 | 劣势 |
|--------|-------------|------|------|
| **Vultr** | ~$48 | 部署快、IP池大、支持自定义ISO | 国内访问慢 |
| **DigitalOcean** | ~$48 | 简单易用、文档好 | IP容易被标记 |
| **Hetzner** | ~€15 (~$16) | 性价比极高 | 仅欧洲机房 |
| **阿里云** | ¥200-400 | 国内快、稳定 | 贵、IP可能被标记 |
| **腾讯云** | ¥150-300 | 国内快 | 同上 |
| **AWS EC2** | ~$70+ | 全球覆盖、可靠 | 最贵 |

### 我的建议

- **测试阶段**：Vultr 或 Hetzner（便宜，可随时销毁）
- **生产阶段**：根据目标平台选择
  - 国内平台(小红书/抖音)：阿里云/腾讯云
  - 海外平台(Instagram/TikTok)：Vultr/Hetzner

---

## 第二阶段：VPS 初始化脚本

### 2.1 创建初始化脚本

在新VPS上运行以下脚本完成基础配置：

```bash
#!/bin/bash
# vps-init.sh - VPS初始化脚本

set -e

echo "=== 1. 系统更新 ==="
apt update && apt upgrade -y

echo "=== 2. 安装基础依赖 ==="
apt install -y \
    curl wget git vim htop \
    python3 python3-pip python3-venv \
    xvfb x11vnc fluxbox \
    chromium-browser \
    unzip jq

echo "=== 3. 安装 Docker ==="
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

echo "=== 4. 创建工作目录 ==="
mkdir -p /opt/axon
mkdir -p /opt/adspower
mkdir -p /data/profiles
mkdir -p /data/artifacts

echo "=== 5. 配置防火墙 ==="
ufw allow 22/tcp      # SSH
ufw allow 8080/tcp    # Browser Worker API
ufw allow 50325/tcp   # AdsPower API (仅内网访问)
ufw --force enable

echo "=== 6. 创建 axon 用户 ==="
useradd -m -s /bin/bash axon || true
usermod -aG docker axon

echo "=== 初始化完成 ==="
echo "请手动安装 AdsPower 并配置 Browser Worker"
```

### 2.2 安装 AdsPower

AdsPower 需要手动安装（有GUI安装界面）：

```bash
# 方法1: 下载官方安装包
cd /opt/adspower
wget https://adspower.net/download/AdsPower-linux.zip
unzip AdsPower-linux.zip

# 方法2: 使用 Xvfb 虚拟显示运行（无头模式）
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &
./AdsPower
```

> **注意**: AdsPower 需要激活许可证。确保你有足够的Profile配额。

### 2.3 配置 AdsPower 无头启动

创建 systemd 服务：

```bash
# /etc/systemd/system/adspower.service
[Unit]
Description=AdsPower Browser
After=network.target

[Service]
Type=simple
User=axon
Environment=DISPLAY=:99
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 &
ExecStart=/opt/adspower/AdsPower --headless
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
systemctl daemon-reload
systemctl enable adspower
systemctl start adspower
```

---

## 第三阶段：部署 Browser Worker

### 3.1 克隆代码

```bash
cd /opt/axon
git clone <your-repo-url> browser-worker
cd browser-worker
```

### 3.2 配置环境

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3.3 创建配置文件

```bash
# /opt/axon/browser-worker/config.yaml
server:
  host: 0.0.0.0
  port: 8080

adspower:
  api_url: http://127.0.0.1:50325
  timeout: 30

worker:
  artifacts_dir: /data/artifacts
  max_concurrent: 5

# 中央控制器地址（可选）
central:
  url: http://your-central-server.com
  api_key: your-api-key
```

### 3.4 创建 systemd 服务

```bash
# /etc/systemd/system/browser-worker.service
[Unit]
Description=Axon Browser Worker
After=network.target adspower.service

[Service]
Type=simple
User=axon
WorkingDirectory=/opt/axon/browser-worker
Environment=PATH=/opt/axon/browser-worker/.venv/bin
ExecStart=/opt/axon/browser-worker/.venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：
```bash
systemctl daemon-reload
systemctl enable browser-worker
systemctl start browser-worker
```

### 3.5 验证部署

```bash
# 检查服务状态
systemctl status adspower
systemctl status browser-worker

# 测试 API
curl http://localhost:8080/health

# 测试 AdsPower
curl http://localhost:50325/status
```

---

## 第四阶段：批量部署（自动化）

### 4.1 使用 Ansible 批量部署

创建 inventory 文件：

```ini
# inventory.ini
[workers]
vps1 ansible_host=1.2.3.4 ansible_user=root
vps2 ansible_host=5.6.7.8 ansible_user=root
vps3 ansible_host=9.10.11.12 ansible_user=root

[workers:vars]
ansible_python_interpreter=/usr/bin/python3
```

创建 playbook：

```yaml
# deploy-worker.yml
---
- hosts: workers
  become: yes
  tasks:
    - name: Run init script
      script: vps-init.sh

    - name: Clone browser-worker repo
      git:
        repo: 'https://github.com/your/browser-worker.git'
        dest: /opt/axon/browser-worker

    - name: Install Python dependencies
      pip:
        requirements: /opt/axon/browser-worker/requirements.txt
        virtualenv: /opt/axon/browser-worker/.venv

    - name: Copy systemd services
      template:
        src: "{{ item }}.service.j2"
        dest: "/etc/systemd/system/{{ item }}.service"
      loop:
        - adspower
        - browser-worker

    - name: Start services
      systemd:
        name: "{{ item }}"
        state: started
        enabled: yes
      loop:
        - adspower
        - browser-worker
```

运行部署：
```bash
ansible-playbook -i inventory.ini deploy-worker.yml
```

### 4.2 使用 Terraform 创建 VPS（示例：Vultr）

```hcl
# main.tf
terraform {
  required_providers {
    vultr = {
      source = "vultr/vultr"
    }
  }
}

provider "vultr" {
  api_key = var.vultr_api_key
}

resource "vultr_instance" "worker" {
  count       = 3
  plan        = "vc2-2c-4gb"  # 2核4G
  region      = "sgp"         # 新加坡
  os_id       = 1743          # Ubuntu 22.04
  label       = "axon-worker-${count.index + 1}"
  hostname    = "worker${count.index + 1}"

  # 初始化脚本
  script_id   = vultr_startup_script.init.id
}

resource "vultr_startup_script" "init" {
  name   = "axon-worker-init"
  script = base64encode(file("vps-init.sh"))
}

output "worker_ips" {
  value = vultr_instance.worker[*].main_ip
}
```

---

## 第五阶段：中央管理与监控

### 5.1 Worker 注册机制

修改 Browser Worker 启动时自动注册到中央服务器：

```python
# src/registration.py
import requests
import socket

def register_worker(central_url: str, api_key: str):
    """启动时向中央服务器注册"""
    payload = {
        "worker_id": socket.gethostname(),
        "ip": get_public_ip(),
        "port": 8080,
        "capabilities": {
            "max_profiles": 20,
            "platforms": ["xiaohongshu", "instagram"]
        }
    }

    resp = requests.post(
        f"{central_url}/api/workers/register",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return resp.json()
```

### 5.2 健康检查

中央服务器定期检查所有 Worker：

```python
# 中央服务器端
async def health_check_all_workers():
    workers = await db.get_all_workers()

    for worker in workers:
        try:
            resp = await httpx.get(
                f"http://{worker.ip}:{worker.port}/health",
                timeout=5
            )
            worker.status = "healthy" if resp.status_code == 200 else "unhealthy"
            worker.last_seen = datetime.utcnow()
        except Exception:
            worker.status = "offline"

    await db.update_workers(workers)
```

### 5.3 监控 Dashboard（TODO）

建议使用：
- **Grafana + Prometheus**：监控系统指标
- **自建 React Dashboard**：管理任务和 Profile

---

## 检查清单

### 单台 VPS 部署检查

- [ ] 系统更新完成
- [ ] Docker 安装并运行
- [ ] AdsPower 安装并激活许可证
- [ ] AdsPower API 可访问 (curl http://localhost:50325/status)
- [ ] Browser Worker 部署完成
- [ ] Worker API 可访问 (curl http://localhost:8080/health)
- [ ] 防火墙配置正确
- [ ] systemd 服务自启动配置

### 集群部署检查

- [ ] 所有 VPS 可通过 SSH 访问
- [ ] Ansible 或 Terraform 配置正确
- [ ] 批量部署脚本测试通过
- [ ] 中央服务器可连接所有 Worker
- [ ] 任务分发测试通过

---

## 常见问题

### Q: AdsPower 无法启动
A: 检查 Xvfb 虚拟显示是否运行：`ps aux | grep Xvfb`

### Q: Browser Worker 连接 AdsPower 失败
A: 确保 AdsPower 的 API 端口 50325 开放，且服务已启动

### Q: VPS IP 被目标平台封禁
A: 考虑使用住宅代理(Residential Proxy)，或更换 IP

### Q: 如何查看浏览器画面？
A: 有两种方案：
1. VNC：安装 x11vnc 连接虚拟显示
2. WebRTC：（下一阶段实现）将画面推流到前端

---

## 下一步

1. **WebRTC 前端渲染**：实现远程浏览器画面实时查看
2. **代理集成**：接入 Scrapoxy 管理代理池
3. **Web Dashboard**：开发统一管理界面
