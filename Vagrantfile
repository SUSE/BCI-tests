$setup_system = <<~SCRIPT
  if [[ $(cat /proc/sys/crypto/fips_enabled) -ne 1 ]]; then
      echo "FIPS is not enabled!"
      exit 1
  fi

  cat << EOF > /usr/share/pki/trust/anchors/SUSE_Trust_Root.crt
  -----BEGIN CERTIFICATE-----
  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
  -----END CERTIFICATE-----
  EOF

  update-ca-certificates

  systemctl start docker
  pip install tox
SCRIPT

$fips_test_script = <<~SCRIPT
  cd /vagrant/
  #prevent setuptools_scm barfing because it cannot obtain the version from git
  export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.1

  for runtime in docker podman; do
      CONTAINER_RUNTIME=${runtime} tox -e fips -- -n auto
  done
SCRIPT

$registered_test_script = <<~SCRIPT
  if [[ ! -n "${REGCODE}" ]]; then
      echo "environment variable REGCODE is unset or empty"
      exit 1
  fi
  SUSEConnect --regcode ${REGCODE}
  cd /vagrant/
  for runtime in docker podman; do
      export CONTAINER_RUNTIME=${runtime}
      # retry the build stage a few times as sometimes it fails due to
      # networking issues
      tox -e build -- -k container_build_and_repo -n auto
  done
SCRIPT

Vagrant.configure('2') do |config|
  config.vm.box = 'SLES15-SP3-Vagrant.x86_64'
  config.vm.box_url = 'https://download.opensuse.org/repositories/home:/dancermak:/SLE-15-SP3/images/boxes/SLES15-SP3-Vagrant.x86_64.json'

  config.vm.synced_folder '.',
                          '/vagrant',
                          type: 'rsync',
                          rsync__exclude: ['.tox/', '*.egg-info', '*/__pycache__/']

  config.vm.provider :libvirt do |libvirt|
    libvirt.cpus = 4
    libvirt.memory = 4096
  end

  config.vm.provision 'setup system', type: 'shell', inline: $setup_system

  env = { 'OS_VERSION': ENV['OS_VERSION'], "REGCODE": ENV['REGCODE'] }

  config.vm.define 'fips' do |fips|
    fips.vm.provision 'run fips test', type: 'shell',
                                       inline: $fips_test_script,
                                       env: env
  end

  config.vm.define 'registered' do |reg|
    reg.vm.provision 'run build tests', type: 'shell',
                                        inline: $registered_test_script,
                                        env: env
  end
end
