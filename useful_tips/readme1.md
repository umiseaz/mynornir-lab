# GNS3 tap1 add on ubuntu
```
sudo tunctl -t tap1 -u khau
sudo ifconfig tap1 10.255.255.1 netmask 255.255.255.0 up 
sudo iptables -t nat -A POSTROUTING -o wlp1s0 -j MASQUERADE
sudo iptables -A FORWARD -i tap1 -j ACCEPT
echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward

goto gns3 clound add tap1
done
```

# new way
```
sudo ip tuntap add dev tap1 mode tap user khau
sudo ip addr add 10.1.1.254/24 dev tap1
sudo ip link set tap1 up
```

# nmcli
```
# 1. Create the TAP interface assigned to your user
sudo nmcli connection add type tun ifname tap1 con-name tap1 mode tap owner $(id -u khau)

# 2. Set the static IP address
sudo nmcli connection modify tap1 ipv4.addresses 10.1.1.254/24 ipv4.method manual

# 3. Bring it up
sudo nmcli connection up tap1
```
---

```
# ubuntu
```
khau@nuc:~$ lsb_release -a
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 24.04.4 LTS
Release:	24.04
Codename:	noble
```
# python ver installed on ubuntu
```
khau@nuc:~$ python3 --version
Python 3.12.3
```

# use virtual environment
```
# install venv if not yet
sudo apt install python3-venv

# create venv
python3 -m venv ~/nornir-env

# activate
source ~/nornir-env/bin/activate

# now install
pip install nornir
```
# lab structure
```
(nornir-env) khau@nuc:~/nornir-env/mynornir-lab$ tree
.
├── config.yaml
├── git_push.sh
├── gns3-add-tap.md
├── inventory
│   ├── defaults.yaml
│   ├── groups.yaml
│   └── hosts.yaml
├── nornir.log
├── output
│   ├── 001_output
│   │   └── 001_output-data.log
│   ├── 002a_output
│   │   └── IOU1_drift.txt
│   └── 002_output
│       ├── IOU1_run.cfg
│       └── IOU2_run.cfg
├── README.md
├── scripts
│   ├── 001_script.py
│   ├── 002a_script.py
│   └── 002_script.py
└── templates

8 directories, 15 files
```
# pip install
```
source ~/nornir-env/bin/activate
pip install nornir-netmiko 
pip install netmiko
pip install nornir-napalm napalm
pip install nornir-utils
pip install rich nornir_rich
pip install nornir_jinja2
pip install pyats genie
```

```
# Test bgp.j2 for pe1 only
python3 test_template.py bgp.j2 pe1

# Test bgp.j2 for pe1 and pe2
python3 test_template.py bgp.j2 pe1 pe2

# Test interfaces.j2 for all core routers
python3 test_template.py interfaces.j2 pe1 pe2 p1 p2 rr1 rr2

# Test master.j2 (full config) for one router
python3 test_template.py master.j2 pe1
```
```
# 1. Update YAML
# 2. Test the specific template
python3 test_template.py bgp.j2 pe1

# 3. Dry run full render
python3 render.py --dry-run

# 4. Push
python3 render.py

# 5. Save
python3 save.py
```