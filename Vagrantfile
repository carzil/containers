Vagrant.configure(2) do |config|
	config.vm.box = 'ubuntu/eoan64'
	config.vm.provision "shell" do |s|
    ssh_pub_key = File.readlines("#{Dir.home}/.ssh/id_rsa.pub").first.strip
    s.inline = <<-SHELL
      echo #{ssh_pub_key} >> /home/vagrant/.ssh/authorized_keys
      echo #{ssh_pub_key} >> /root/.ssh/authorized_keys
      apt-get update -y
      apt-get install -y python3-pip python3
      python3 -m pip install -r /vagrant/requirements.txt
      echo 1 > /proc/sys/net/ipv4/ip_forward
      iptables --flush
      iptables -t nat -A POSTROUTING -o enki0 -j MASQUERADE
      iptables -t nat -A POSTROUTING -o enp0s3 -j MASQUERADE
      ip link add enki0 type bridge
      ip addr add 172.16.0.1/16 dev enki0
      ip link set enki0 up
    SHELL
  end
end
