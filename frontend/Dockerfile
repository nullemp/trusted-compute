# 国内拉取失败时可传构建参数：--build-arg NODE_IMAGE=docker.m.daocloud.io/library/node:18-alpine
ARG NODE_IMAGE=node:18-alpine
FROM ${NODE_IMAGE}

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "start"]
