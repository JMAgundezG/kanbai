FROM node:24-bookworm-slim

# Corepack installs the pnpm version pinned in "packageManager"; the prompt would
# block the build because there is no TTY.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable pnpm

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173

# Sin "--": pnpm se lo pasaría literal a Vite y el flag se perdería.
CMD ["pnpm", "run", "dev", "--host", "0.0.0.0"]
