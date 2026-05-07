# Elasticsearch + IK 中文分词

## 准备 IK 插件包（首次构建必做）

下载 `elasticsearch-analysis-ik-8.13.4.zip` 放到本目录（`docker/elasticsearch/`）。

### 下载源（任选其一可用即可）

1. **官方 InfiniLabs 直链**
   https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-8.13.4.zip

2. **GitHub Release**
   https://github.com/infinilabs/analysis-ik/releases/download/v8.13.4/elasticsearch-analysis-ik-8.13.4.zip

3. **GitHub Release（ghproxy 加速）**
   https://ghproxy.com/https://github.com/infinilabs/analysis-ik/releases/download/v8.13.4/elasticsearch-analysis-ik-8.13.4.zip

4. **InfiniLabs 备用**
   https://get.infini.cloud/elasticsearch/analysis-ik/8.13.4

### 命令行下载示例

```powershell
# PowerShell
Invoke-WebRequest `
  -Uri "https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-8.13.4.zip" `
  -OutFile "D:\atguigu\data-agent\docker\elasticsearch\elasticsearch-analysis-ik-8.13.4.zip"
```

## 构建

放好 zip 后回到项目根目录执行：

```powershell
docker compose up -d --build
```

## 验证

```powershell
docker exec data-agent-es bin/elasticsearch-plugin list
# 应输出：analysis-ik
```
