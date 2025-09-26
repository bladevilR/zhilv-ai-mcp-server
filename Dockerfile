# 使用一个更新、稳定且轻量的Python 3.11镜像作为基础
FROM python:3.11-slim

# 在容器内创建一个工作目录
WORKDIR /app

# 将依赖文件复制进去
COPY requirements.txt .

# 安装所有依赖库，--no-cache-dir 参数可以减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 将你本地的所有文件（包括data文件夹）都复制到容器的工作目录中
COPY . .

# 向外界声明，容器内的这个端口将对外提供服务
EXPOSE 7860

# 容器启动时要执行的最终命令
# 启动uvicorn，监听所有网络接口的7860端口
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
