FROM node:20-alpine

WORKDIR /app

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source
COPY . .

# Build Next.js application
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000/api}
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
