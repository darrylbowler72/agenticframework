FROM jenkins/jenkins:lts

USER root

# Install plugins (let Jenkins resolve compatible versions)
RUN jenkins-plugin-cli --plugins \
    configuration-as-code \
    workflow-aggregator \
    git \
    github \
    matrix-auth

# Copy Jenkins Configuration as Code to a location that won't be hidden by EFS mount
COPY jenkins.yaml /usr/share/jenkins/ref/jenkins.yaml

# Create entrypoint script to copy config to EFS if it doesn't exist
RUN echo '#!/bin/bash' > /usr/local/bin/jenkins-entrypoint.sh && \
    echo 'if [ ! -f /var/jenkins_home/jenkins.yaml ]; then' >> /usr/local/bin/jenkins-entrypoint.sh && \
    echo '  cp /usr/share/jenkins/ref/jenkins.yaml /var/jenkins_home/jenkins.yaml' >> /usr/local/bin/jenkins-entrypoint.sh && \
    echo 'fi' >> /usr/local/bin/jenkins-entrypoint.sh && \
    echo 'exec /usr/local/bin/jenkins.sh "$@"' >> /usr/local/bin/jenkins-entrypoint.sh && \
    chmod +x /usr/local/bin/jenkins-entrypoint.sh

USER jenkins

ENV CASC_JENKINS_CONFIG=/var/jenkins_home/jenkins.yaml

ENTRYPOINT ["/usr/local/bin/jenkins-entrypoint.sh"]
