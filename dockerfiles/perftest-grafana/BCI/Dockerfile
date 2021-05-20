FROM  registry.opensuse.org/devel/bci/images/bci/golang:1.16

ENV SUMMARY="Grafana is an open source, feature rich metrics dashboard and graph editor" \
    DESCRIPTION="Grafana is an open source, feature rich metrics dashboard and graph editor for Graphite, Elasticsearch, OpenTSDB, Prometheus, InfluxDB." \
    VERSION=7

LABEL name="susehub/grafana" \
      summary="${SUMMARY}" \
      description="${DESCRIPTION}" \
      version="$VERSION" \
      usage="podman run -d --name grafana -p 3000:3000 -v grafana-data:/var/lib/grafana susehub/grafana" \
      maintainer="SUSE Hub Maintainers <hub@suse.com>" \
      help="cat /README.md"

# We don't package performance copilot
RUN zypper ar https://download.opensuse.org/repositories/server:/monitoring/openSUSE_Leap_15.3/server:monitoring.repo && \
    zypper --gpg-auto-import-keys refresh && zypper install -y grafana && mkdir -p  /var/run/grafana && chown -R grafana. /usr/share/grafana  /var/lib/grafana  /var/run/grafana

# COPY root /

VOLUME ["/var/lib/grafana"]
EXPOSE 3000

USER grafana
WORKDIR /usr/share/grafana
#ENTRYPOINT ["/usr/sbin/grafana-server --config=/etc/grafana/grafana.ini --pidfile=/var/run/grafana/grafana-server.pid cfg:default.paths.logs=/var/log/grafana cfg:default.paths.data=/var/lib/grafana cfg:default.paths.plugins=/var/lib/grafana/plugins cfg:default.paths.provisioning=/etc/grafana/provisioning"]
ENTRYPOINT ["/usr/sbin/grafana-server -config /etc/grafana/grafana.ini"]
# This probably needs thousand of arguments
# [Unit]
# Description=Grafana instance
# Documentation=http://docs.grafana.org
# Wants=network-online.target
# After=network-online.target
# After=postgresql.service mariadb.service mysqld.service

# [Service]
# EnvironmentFile=/etc/sysconfig/grafana-server
# User=grafana
# Group=grafana
# Type=notify
# Restart=on-failure
# WorkingDirectory=/usr/share/grafana
# RuntimeDirectory=grafana
# RuntimeDirectoryMode=0750
# ExecStart=/usr/sbin/grafana-server                                                  \
#                             --config=${CONF_FILE}                                   \
#                             --pidfile=${PID_FILE_DIR}/grafana-server.pid            \
#                             --packaging=rpm                                         \
#                             cfg:default.paths.logs=${LOG_DIR}                       \
#                             cfg:default.paths.data=${DATA_DIR}                      \
#                             cfg:default.paths.plugins=${PLUGINS_DIR}                \
#                             cfg:default.paths.provisioning=${PROVISIONING_CFG_DIR}  

# LimitNOFILE=10000
# TimeoutStopSec=20

# [Install]
# WantedBy=multi-user.target