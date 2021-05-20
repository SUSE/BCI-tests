FROM registry.stage.redhat.io/ubi8/ubi:8.4

ENV SUMMARY="Grafana is an open source, feature rich metrics dashboard and graph editor" \
    DESCRIPTION="Grafana is an open source, feature rich metrics dashboard and graph editor for Graphite, Elasticsearch, OpenTSDB, Prometheus, InfluxDB and Performance Co-Pilot." \
    VERSION=7

LABEL name="rhel8/grafana" \
      summary="${SUMMARY}" \
      description="${DESCRIPTION}" \
      version="$VERSION" \
      usage="podman run -d --name grafana -p 3000:3000 -v grafana-data:/var/lib/grafana registry.redhat.io/rhel8/grafana" \
      maintainer="Grafana Maintainers <grafana-maint@redhat.com>" \
      help="cat /README.md" \
      com.redhat.component="grafana-container" \
      io.k8s.display-name="Grafana" \
      io.k8s.description="${DESCRIPTION}" \
      io.openshift.expose-services="3000:grafana" \
      io.openshift.tags="grafana,monitoring,dashboard"

RUN useradd -u 1001 -g 0 -r -d /usr/share/grafana -s /sbin/nologin grafana && \
    dnf install -y --setopt=tsflags=nodocs grafana grafana-pcp && \
    dnf clean all && \
    chgrp -R 0 /etc/grafana /var/lib/grafana /var/log/grafana && \
    chmod -R g=u /var/lib/grafana /var/log/grafana && \
    mv /var/lib/grafana/plugins/performancecopilot-pcp-app /usr/share/performancecopilot-pcp-app

# COPY root /

VOLUME ["/var/lib/grafana"]
EXPOSE 3000

USER 1001
WORKDIR /usr/share/grafana
ENTRYPOINT ["/usr/bin/run-grafana"]