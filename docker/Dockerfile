
FROM jenkins/jenkins:lts

USER root

# Install Git, Node.js, and Docker CLI
RUN apt-get update && apt-get install -y git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && apt-get install -y docker.io \
    && groupadd -f docker && usermod -aG docker jenkins \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

USER jenkins
