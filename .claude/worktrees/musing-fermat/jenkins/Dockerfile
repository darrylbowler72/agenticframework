FROM jenkins/jenkins:lts

USER root

# Install plugins (let Jenkins resolve compatible versions)
RUN jenkins-plugin-cli --plugins \
    configuration-as-code \
    workflow-aggregator \
    git \
    github \
    matrix-auth

USER jenkins

# Copy Jenkins Configuration as Code
COPY jenkins.yaml /var/jenkins_home/jenkins.yaml

ENV CASC_JENKINS_CONFIG=/var/jenkins_home/jenkins.yaml
