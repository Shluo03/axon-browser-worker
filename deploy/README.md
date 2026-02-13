# 🚀 VM Deployment Guide

## 📋 前提条件

在开始之前，确保你有：

- [ ] AWS 账号 + 访问密钥 (Access Key + Secret Key)
- [ ] AdsPower 账号 + 许可证
- [ ] 本地安装 Terraform (`brew install terraform` 或 [下载](https://www.terraform.io/downloads))
- [ ] 本地安装 AWS CLI (`brew install awscli` 或 [安装指南](https://aws.amazon.com/cli/))
- [ ] SSH 密钥对（会在步骤中创建）

---

## 🎯 快速开始（5分钟部署）

### Step 1: 配置 AWS 凭证

```bash
# 配置 AWS 访问密钥
aws configure
# 输入:
#   AWS Access Key ID: AKIA...
#   AWS Secret Access Key: xxxxx
#   Default region: ap-northeast-1  (东京，或其他区域)
#   Default output format: json
```

### Step 2: 创建 SSH 密钥对

```bash
# 在 AWS 控制台创建，或用命令行：
aws ec2 create-key-pair \
  --key-name axon-worker \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/axon-worker.pem

chmod 400 ~/.ssh/axon-worker.pem
```

### Step 3: 配置 Terraform

```bash
cd deploy/terraform

# 复制配置模板
cp terraform.tfvars.example terraform.tfvars

# 编辑配置
vim terraform.tfvars
```

**terraform.tfvars 内容：**
```hcl
aws_region       = "ap-northeast-1"  # 东京
instance_type    = "t3.large"        # 2核8G，测试够用
instance_count   = 1                 # 先部署1台
key_name         = "axon-worker"     # 刚才创建的密钥名
allowed_ssh_cidr = "0.0.0.0/0"       # 或改成你的IP/32
project_name     = "axon-worker"
```

### Step 4: 部署 EC2

```bash
# 初始化 Terraform
terraform init

# 预览将创建的资源
terraform plan

# 部署！
terraform apply
# 输入 yes 确认
```

**等待约 2-3 分钟，输出类似：**
```
Apply complete! Resources: 4 added.

Outputs:

ssh_commands = [
  "ssh -i ~/.ssh/axon-worker.pem ubuntu@54.178.xxx.xxx"
]
worker_api_urls = [
  "http://54.178.xxx.xxx:8080"
]
worker_public_ips = [
  "54.178.xxx.xxx"
]
```

### Step 5: SSH 登录并安装 AdsPower

```bash
# SSH 登录
ssh -i ~/.ssh/axon-worker.pem ubuntu@<VM_IP>

# 等待 cloud-init 完成（约5分钟）
tail -f /var/log/cloud-init-output.log
# 看到 "Cloud-init completed" 后按 Ctrl+C

# 克隆你的代码
sudo -u axon git clone https://github.com/YOUR_USERNAME/axon-browser-worker.git /opt/axon/browser-worker

# 运行安装脚本
cd /opt/axon/browser-worker
sudo -u axon chmod +x deploy/scripts/*.sh
sudo -u axon ./deploy/scripts/setup-worker.sh
```

### Step 6: 安装 AdsPower（手动）

```bash
# 下载 AdsPower
cd /tmp
# 从 https://www.adspower.com/download 获取最新 Linux 版本链接
wget "https://adspower.com/download/AdsPower-Global-xxx-x64.tar.gz"

# 解压安装
sudo mkdir -p /opt/adspower
sudo tar -xzf AdsPower-Global-*.tar.gz -C /opt/adspower --strip-components=1
sudo chown -R axon:axon /opt/adspower

# 启动 AdsPower (在虚拟显示上)
DISPLAY=:99 /opt/adspower/AdsPower &
```

### Step 7: 通过 VNC 激活 AdsPower

AdsPower 需要登录激活许可证，必须通过图形界面操作：

**macOS:**
```bash
open vnc://<VM_IP>:5900
```

**Windows:**
使用 VNC Viewer 连接 `<VM_IP>:5900`

**Linux:**
```bash
vncviewer <VM_IP>:5900
```

在 VNC 窗口中：
1. 看到 AdsPower 登录界面
2. 输入你的账号密码
3. 激活许可证
4. 创建至少一个 Profile

### Step 8: 启动服务

```bash
# 回到 SSH 终端
# 创建 AdsPower systemd 服务
sudo tee /etc/systemd/system/adspower.service > /dev/null << 'EOF'
[Unit]
Description=AdsPower Browser
After=network.target xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=axon
Environment=DISPLAY=:99
WorkingDirectory=/opt/adspower
ExecStart=/opt/adspower/AdsPower
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启动所有服务
sudo systemctl daemon-reload
sudo systemctl enable adspower browser-worker
sudo systemctl start adspower browser-worker

# 检查状态
sudo ./deploy/scripts/health-check.sh
```

### Step 9: 验证部署

```bash
# 检查 AdsPower API
curl http://localhost:50325/status

# 检查 Browser Worker API
curl http://localhost:8080/health

# 从外部访问（用你的本地电脑）
curl http://<VM_IP>:8080/health
```

**成功输出：**
```json
{
  "status": "ok",
  "profiles_summary": {
    "healthy": 0,
    "cooling": 0,
    "needs_human": 0,
    "disabled": 0
  }
}
```

---

## 🎉 部署完成！

你现在有：
- ✅ 运行在 AWS EC2 上的 VM
- ✅ AdsPower 反指纹浏览器
- ✅ Browser Worker HTTP API
- ✅ VNC 远程访问（用于调试）

**访问地址：**
- Worker API: `http://<VM_IP>:8080`
- VNC: `vnc://<VM_IP>:5900`

---

## 📖 常用命令

### 服务管理
```bash
# 查看状态
sudo systemctl status browser-worker
sudo systemctl status adspower

# 重启服务
sudo systemctl restart browser-worker
sudo systemctl restart adspower

# 查看日志
journalctl -u browser-worker -f
journalctl -u adspower -f
```

### Terraform 管理
```bash
# 查看当前资源
terraform show

# 销毁所有资源（删除 VM）
terraform destroy

# 更新配置后重新应用
terraform apply
```

### 测试任务
```bash
# 运行测试任务
curl -X POST http://<VM_IP>:8080/run-task \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test_001",
    "profile_id": "YOUR_PROFILE_ID",
    "task_type": "page_probe",
    "params": {
      "url": "https://www.google.com"
    }
  }'
```

---

## ⚠️ 故障排除

### AdsPower 无法启动
```bash
# 检查虚拟显示
systemctl status xvfb
ps aux | grep Xvfb

# 手动启动测试
DISPLAY=:99 /opt/adspower/AdsPower
```

### Browser Worker 连接失败
```bash
# 检查 AdsPower API
curl http://127.0.0.1:50325/status

# 检查端口
netstat -tlnp | grep -E '50325|8080'
```

### VNC 连接不上
```bash
# 检查 VNC 服务
systemctl status x11vnc

# 检查防火墙
sudo ufw status
```

---

## 💰 成本估算

| 配置 | 规格 | 月费用 (ap-northeast-1) |
|------|------|------------------------|
| t3.large | 2核8G | ~$60/月 |
| t3.xlarge | 4核16G | ~$120/月 |
| EIP | 弹性IP | ~$3.6/月 |
| EBS | 80GB gp3 | ~$8/月 |
| **总计** | t3.large | **~$72/月** |

> 提示：用完记得 `terraform destroy` 销毁资源，避免持续计费！

---

## 📁 文件结构

```
deploy/
├── README.md              # 本文档
├── terraform/
│   ├── main.tf            # Terraform 主配置
│   ├── cloud-init.yaml    # VM 初始化脚本
│   └── terraform.tfvars.example
├── ansible/
│   ├── inventory.ini.example
│   ├── deploy.yml         # Ansible playbook
│   └── templates/
│       ├── config.yaml.j2
│       └── browser-worker.service.j2
└── scripts/
    ├── setup-worker.sh    # Worker 安装脚本
    ├── install-adspower.sh
    └── health-check.sh    # 健康检查
```

---

## 🔜 下一步

1. **测试自动化任务** - 用 API 运行一些任务
2. **WebRTC 画面串流** - 实现远程实时查看浏览器
3. **扩容** - 修改 `instance_count` 部署更多 VM
4. **中央控制** - 搭建控制面板管理所有 Worker
