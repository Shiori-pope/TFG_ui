# 公网访问配置指南

## 📋 配置步骤

### 1️⃣ 修改 Flask 应用绑定地址 ✅
已完成！`app.py` 现在绑定到 `0.0.0.0:5001`，可接受所有网络接口的连接。

### 2️⃣ 开放 Windows 防火墙

**方法一：使用脚本（推荐）**
```powershell
# 右键点击 PowerShell，选择"以管理员身份运行"
.\open_firewall.ps1
```

**方法二：手动配置**
1. 打开 Windows Defender 防火墙
2. 点击"高级设置"
3. 入站规则 → 新建规则
4. 选择"端口" → TCP → 特定本地端口：5001
5. 允许连接 → 完成

### 3️⃣ 获取访问地址

运行 Flask 应用后，会自动显示：
- **本地访问**: `http://127.0.0.1:5001`
- **局域网访问**: `http://<本机IP>:5001`
- **公网访问**: `http://<公网IP>:5001`

### 4️⃣ 查看本机 IP 地址

```powershell
# 查看局域网 IP
ipconfig

# 查看公网 IP
curl ifconfig.me
# 或访问 https://ip.cn
```

### 5️⃣ 路由器端口转发（可选）

如果需要从外网访问，且你的设备在路由器后面：

1. 登录路由器管理界面（通常是 192.168.1.1 或 192.168.0.1）
2. 找到"端口转发"或"虚拟服务器"设置
3. 添加规则：
   - 外部端口: 5001
   - 内部 IP: <你的电脑局域网IP>
   - 内部端口: 5001
   - 协议: TCP

## 🌐 访问测试

### 局域网测试
同一网络下的其他设备访问：
```
http://<你的局域网IP>:5001
```

### 公网测试（如果你有公网IP）
```
http://<你的公网IP>:5001
```

## ⚠️ 安全建议

### 基础安全
1. **仅在可信网络使用**：开发/测试环境
2. **定期关闭端口**：不用时运行 `close_firewall.ps1`
3. **监控访问日志**：检查异常访问

### 生产环境建议
如需长期公网访问，建议：

1. **使用 Nginx 反向代理**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **配置 HTTPS**
   - 使用 Let's Encrypt 免费证书
   - 强制 HTTPS 访问

3. **添加访问控制**
   - IP 白名单
   - 用户认证
   - 限流保护

4. **使用云服务**
   - 阿里云/腾讯云 ECS
   - 内网穿透：frp/ngrok
   - CDN 加速

## 🔧 故障排查

### 无法从局域网访问
```powershell
# 1. 检查防火墙规则
Get-NetFirewallRule -DisplayName "Flask App Port 5001"

# 2. 检查端口监听
netstat -ano | findstr :5001

# 3. 测试本地访问
curl http://127.0.0.1:5001
```

### 无法从公网访问
1. 确认是否有公网 IP（运营商可能使用内网 IP）
2. 检查路由器端口转发配置
3. 测试路由器外部 IP 是否正确

### 检查防火墙状态
```powershell
# 查看所有防火墙规则
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*Flask*"}

# 删除规则（如需重新配置）
Remove-NetFirewallRule -DisplayName "Flask App Port 5001"
```

## 📝 快速命令

```powershell
# 启动服务
python app.py

# 开放防火墙（管理员权限）
.\open_firewall.ps1

# 查看本机IP
ipconfig

# 查看公网IP
curl ifconfig.me

# 测试端口
Test-NetConnection -ComputerName <IP> -Port 5001

# 关闭防火墙
.\close_firewall.ps1
```

## 🚀 快速启动

1. 右键点击 PowerShell，选择"以管理员身份运行"
2. 运行 `.\open_firewall.ps1` 开放端口
3. 运行 `python app.py` 启动服务
4. 使用显示的 IP 地址访问

完成！🎉
