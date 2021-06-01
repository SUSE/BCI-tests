$test_script = <<-SCRIPT
if [[ $(cat /proc/sys/crypto/fips_enabled) -ne 1 ]]; then
    echo "FIPS is not enabled!"
    exit 1
fi
systemctl start docker
cd /vagrant/
python3.9 -m ensurepip --upgrade --default-pip
pip install --upgrade tox
CONTAINER_RUNTIME=docker tox -e base
CONTAINER_RUNTIME=podman tox -e base
SCRIPT

Vagrant.configure("2") do |config|
  config.vm.box = "SLES15-SP3-Vagrant.x86_64"
  config.vm.box_url = "https://download.opensuse.org/repositories/home:/dancermak:/SLE-15-SP3/images/boxes/SLES15-SP3-Vagrant.x86_64.json"

  config.vm.provision "shell", inline: $test_script
end
