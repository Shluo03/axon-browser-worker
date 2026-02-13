# 🚀 Manual VM Setup Guide

手动部署 Browser Worker 的完整步骤指南。

---

## 📋 前提条件

- [ ] AWS 账号 ## ask Shen for account info
- [ ] AdsPower 账号 + API Key  ## ask Shen for account info
- [ ] Mac/Linux 本地环境

---

## Part 1: AWS EC2 创建

### 1.1 登录 AWS Console

1. 打开 https://console.aws.amazon.com
2. 选择区域 **Asia Pacific (Tokyo) ap-northeast-1**

### 1.2 创建 EC2 实例

1. 进入 **EC2 > Instances > Launch instances**
2. 配置如下：

| 设置 | 值 |
|------|-----|
| Name | `axon-browser-worker` |
| AMI | Ubuntu Server 24.04 LTS |
| Instance type | `t3.micro` (测试) 或 `t3.large` (生产) |
| Key pair | 创建新的，命名 `axon-worker`，下载 .pem 文件 |
| Network | 允许 SSH (22), 自定义 TCP (5900) |
| Storage | 30 GB gp3 |

3. 点击 **Launch instance**

### 1.3 配置安全组（开放 VNC 端口）

1. 进入 **EC2 > Security Groups**
2. 找到实例使用的安全组（如 `launch-wizard-1`）
3. **Edit inbound rules > Add rule**:
   - Type: `Custom TCP`
   - Port: `5900`
   - Source: `0.0.0.0/0`
4. **Save rules**

### 1.4 配置 SSH 密钥

```bash

cp ~/Downloads/axon-worker.pem ~/.ssh/axon-worker.pem


chmod 600 ~/.ssh/axon-worker.pem
```

---

## Part 2: 服务器环境配置

### 2.1 SSH 连接服务器

```bash
# 替换 <VM_IP> 为你的 EC2 公网 IP
ssh -i ~/.ssh/axon-worker.pem ubuntu@<VM_IP>
```

### 2.2 安装系统依赖

```bash
sudo apt update && sudo apt install -y \
  xvfb \
  x11vnc \
  xfonts-base \
  xfonts-75dpi \
  xfonts-100dpi \
  libgtk-3-0 \
  libnotify4 \
  libnss3 \
  libxss1 \
  libasound2 \
  libgbm1 \
  fonts-noto-cjk \
  python3-pip \
  python3-venv \
  git \
  curl \
  wget \
  unzip
```

### 2.3 配置虚拟显示器 (Xvfb)

```bash
# 创建 Xvfb systemd 服务
sudo tee /etc/systemd/system/xvfb.service > /dev/null << 'EOF'
[Unit]
Description=X Virtual Frame Buffer
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable xvfb
sudo systemctl start xvfb

# 验证
ps aux | grep Xvfb
```

---

## Part 3: 安装 AdsPower

### 3.1 下载 AdsPower

由于服务器无法直接下载，需要在本地下载后上传：

**在本地 Mac 终端：**
```bash
# 1. 从 https://www.adspower.com/download 下载 Linux .deb 版本
# 2. 上传到服务器
scp -i ~/.ssh/axon-worker.pem ~/Downloads/AdsPower-Global-*.deb ubuntu@<VM_IP>:/tmp/
```

### 3.2 安装 AdsPower

**在服务器 SSH 终端：**
```bash

sudo dpkg -i /tmp/AdsPower-Global-*.deb

sudo apt install -f -y


ls -la "/opt/AdsPower Global/"
```

### 3.3 获取 AdsPower API Key

1. 登录 AdsPower 官网
2. 进入 **账户设置 > API**
3. 复制你的 API Key

---

## Part 4: 启动服务

### 4.1 启动 VNC 服务器

```bash
# 启动 x11vnc（密码设为 1234，可自定义）
x11vnc -display :99 -forever -shared -rfbport 5900 -passwd 1234 &
```

### 4.2 启动 AdsPower (GUI 模式，首次激活用)

```bash
DISPLAY=:99 /opt/AdsPower\ Global/adspower_global &
```

### 4.3 VNC 连接激活 AdsPower

**在本地 Mac 终端：**
```bash
open vnc://<VM_IP>:5900
# 密码: 1234
```

在 VNC 窗口中：
1. 登录 AdsPower 账号
2. 确保至少有一个 Profile（浏览器配置）
3. 点击 **Open** 测试浏览器能否打开（会自动下载内核）

### 4.4 切换到 API 模式

```bash
# 关闭 GUI 模式
pkill -f adspower

# 用 API 模式启动（替换 <YOUR_API_KEY>）
DISPLAY=:99 /opt/AdsPower\ Global/adspower_global --headless=true --api-key=<YOUR_API_KEY> &

# 验证 API
curl "http://localhost:50325/api/v1/user/list"
```

**成功输出示例：**
```json
{"data":{"list":[{"name":"profile_name","user_id":"k197eg5j",...}],"page":1},"code":0,"msg":"Success"}
```

---

## Part 5: 部署 Browser Worker

### 5.1 克隆代码

```bash
cd ~
git clone https://github.com/Shluo03/axon-browser-worker.git
cd axon-browser-worker
```

### 5.2 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5.3 运行测试

```bash
python test_integration.py
```

**成功输出：**
```
==================================================
Axon Browser Worker Integration Test
==================================================
1. Testing AdsPower client...
   AdsPower is running
   Found 1 profiles

2. Testing browser session...
   Connected to browser
   IP: {"origin": "13.192.207.97"}
   Session closed cleanly

3. Testing humanized actions...
   Humanized scroll complete

4. Testing platform module...
```

---

## Part 6: 配置开机自启（可选）

### 6.1 AdsPower 服务

```bash
sudo tee /etc/systemd/system/adspower.service > /dev/null << 'EOF'
[Unit]
Description=AdsPower Browser
After=network.target xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=ubuntu
Environment=DISPLAY=:99
ExecStart=/opt/AdsPower Global/adspower_global --headless=true --api-key=<YOUR_API_KEY>
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable adspower
sudo systemctl start adspower
```

### 6.2 VNC 服务

```bash
sudo tee /etc/systemd/system/x11vnc.service > /dev/null << 'EOF'
[Unit]
Description=x11vnc VNC Server
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=ubuntu
Environment=DISPLAY=:99
ExecStart=/usr/bin/x11vnc -display :99 -forever -shared -rfbport 5900 -passwd 1234
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable x11vnc
sudo systemctl start x11vnc
```

---

## 📖 常用命令速查

### 连接服务器
```bash
ssh -i ~/.ssh/axon-worker.pem ubuntu@<VM_IP>
```

### 连接 VNC
```bash
# Mac
open vnc://<VM_IP>:5900

# Linux
vncviewer <VM_IP>:5900
```

### 服务管理
```bash
# 查看状态
sudo systemctl status xvfb
sudo systemctl status adspower
sudo systemctl status x11vnc

# 重启服务
sudo systemctl restart adspower

# 查看日志
journalctl -u adspower -f
```

### AdsPower API
```bash
# 查看 Profile 列表
curl "http://localhost:50325/api/v1/user/list"

# 启动浏览器
curl "http://localhost:50325/api/v1/browser/start?user_id=<PROFILE_ID>"

# 关闭浏览器
curl "http://localhost:50325/api/v1/browser/stop?user_id=<PROFILE_ID>"
```

### Browser Worker
```bash
cd ~/axon-browser-worker
source .venv/bin/activate
python test_integration.py
```

---

## ⚠️ 故障排除

### SSH 连接失败
```bash
# 检查密钥权限
chmod 600 ~/.ssh/axon-worker.pem

# 密钥格式错误？重新从 AWS 下载
```

### VNC 连接不上
```bash
# 检查 x11vnc 是否运行
ps aux | grep x11vnc

# 检查安全组是否开放 5900 端口
# AWS Console > EC2 > Security Groups > Inbound rules
```

### AdsPower API 无响应
```bash
# 检查进程
ps aux | grep adspower

# 检查端口
netstat -tlnp | grep 50325

# 重启
pkill -f adspower
DISPLAY=:99 /opt/AdsPower\ Global/adspower_global --headless=true --api-key=<YOUR_API_KEY> &
```

### 浏览器内核下载失败
```bash
# 用 GUI 模式手动下载
pkill -f adspower
DISPLAY=:99 /opt/AdsPower\ Global/adspower_global &

# VNC 连接后手动点击 Open 触发下载
```

---

---

## 🔗 相关链接

- [AdsPower 官网](https://www.adspower.com)
- [AdsPower API 文档](https://localapi-doc.adspower.com)
- [AWS EC2 文档](https://docs.aws.amazon.com/ec2/)

---

```
