import boto3
import os
from os import getenv
from dotenv import load_dotenv
import logging
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig
import argparse
from pprint import pprint
load_dotenv()
import time
import urllib
parser = argparse.ArgumentParser()
parser.add_argument('-npu', type=int, help='number of public subnet')
parser.add_argument('-npr', type=int, help='number of private subnet')
parser.add_argument('--create_vpc_with_subnets', "-cvws", nargs='?', const='true', help='create vpc with subnets' )
parser.add_argument('--create_vpc', "-cv", nargs='?', const='true', help='create vpc' )
parser.add_argument('--tag_vpc', "-tv", type=str, help='Name of vpc')
parser.add_argument('--vpc_id', "-vi", type=str, help='vpc ID')
parser.add_argument('--subnet_id', "-si", type=str, help='subnet ID')
parser.add_argument('--key_pair_name', "-kpn", type=str, help='key pair name')
parser.add_argument('--create_IGW', "-cIGW", nargs='?', const='true', help='create IGW' )
parser.add_argument('--attach_IGW', "-aIGW", nargs='?', const='true', help='attach IGW to vpc' )
s3 = boto3.client('s3')
args = parser.parse_args()

ec2_client = boto3.client(
  "ec2",
  aws_access_key_id=getenv("aws_access_key_id"),
  aws_secret_access_key=getenv("aws_secret_access_key"),
  aws_session_token=getenv("aws_session_token"),
  region_name=getenv("aws_region_name")
)

def create_vpc():
  result = ec2_client.create_vpc(CidrBlock="10.22.0.0/16")
  vpc = result.get("Vpc")
  print(vpc)
  vpc = result.get("Vpc")
  vpc_id = vpc.get("VpcId")

def add_name_tag(vpc_id):
  ec2_client.create_tags(Resources=[vpc_id],
                         Tags=[{
                           "Key": "Name",
                           "Value": args.tag_vpc
                         }])
  print(f'{args.tag_vpc} tag created')
def create_igw():
  result = ec2_client.create_internet_gateway()
  print("InternetGateway created")
  return result.get("InternetGateway").get("InternetGatewayId")
def create_or_get_igw(vpc_id):
  igw_id = None
  igw_response = ec2_client.describe_internet_gateways(
    Filters=[{
      'Name': 'attachment.vpc-id',
      'Values': [vpc_id]
    }])

  if 'InternetGateways' in igw_response and igw_response['InternetGateways']:
    igw = igw_response['InternetGateways'][0]
    igw_id = igw['InternetGatewayId']
  else:
    response = ec2_client.create_internet_gateway()
    pprint(response)
    igw = response.get("InternetGateway")
    igw_id = igw.get("InternetGatewayId")
    response = ec2_client.attach_internet_gateway(InternetGatewayId=igw_id,
                                                  VpcId=vpc_id)
    print("attached")
    pprint(response)
  return igw_id
def create_route_table_with_route(vpc_id, route_table_name, igw_id):
  response = ec2_client.create_route_table(VpcId=vpc_id)
  route_table = response.get("RouteTable")
  pprint(route_table)
  route_table_id = route_table.get("RouteTableId")
  print("Route table id", route_table_id)
  time.sleep(2)
  ec2_client.create_tags(
    Resources=[route_table_id],
    Tags=[
      {
        "Key": "Name",
        "Value": route_table_name
      },
    ],
  )
  response = ec2_client.create_route(
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=igw_id,
    RouteTableId=route_table_id,
  )
  return route_table_id
def associate_route_table_to_subnet(route_table_id, subnet_id):
  response = ec2_client.associate_route_table(RouteTableId=route_table_id,
                                              SubnetId=subnet_id)
  print("Route table associated")
  pprint(response)
def enable_auto_public_ips(subnet_id, action):
  new_state = True if action == "enable" else False
  response = ec2_client.modify_subnet_attribute(
    MapPublicIpOnLaunch={"Value": new_state}, SubnetId=subnet_id)
  print("Public IP association state changed to", new_state)
def create_route_table_without_route(vpc_id):
  response = ec2_client.create_route_table(VpcId=vpc_id)
  route_table = response.get("RouteTable")
  pprint(route_table)
  route_table_id = route_table.get("RouteTableId")
  print("Route table id", route_table_id)
  time.sleep(2)
  ec2_client.create_tags(
    Resources=[route_table_id],
    Tags=[
      {
        "Key": "Name",
        "Value": "private-route-table"
      },
    ],
  )
  return route_table_id
def attach_igw_to_vpc(vpc_id, igw_id):
  ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
def create_subnet(vpc_id, cidr_block, subnet_name):
  time.sleep(2)
  response = ec2_client.create_subnet(VpcId=vpc_id, CidrBlock=cidr_block)
  subnet = response.get("Subnet")
  pprint(subnet)
  subnet_id = subnet.get("SubnetId")
  time.sleep(2)
  ec2_client.create_tags(
    Resources=[subnet_id],
    Tags=[
      {
        "Key": "Name",
        "Value": subnet_name
      },
    ],
  )
  return subnet_id
def create_key_pair(key_name):
  response = ec2_client.create_key_pair(KeyName=key_name,
                                        KeyType="rsa",
                                        KeyFormat="pem")
  key_id = response.get("KeyPairId")
  with open(f"{key_name}.pem", "w") as file:
    file.write(response.get("KeyMaterial"))
  print("Key pair id - ", key_id)
  return key_id
def create_security_group(name, description, VPC_ID):
  response = ec2_client.create_security_group(Description=description,
                                              GroupName=name,
                                              VpcId=VPC_ID)
  group_id = response.get("GroupId")

  print("Security Group Id - ", group_id)

  return group_id



def get_my_public_ip():
  external_ip = urllib.request.urlopen("https://ident.me").read().decode(
    "utf8")
  print("Public ip - ", external_ip)

  return external_ip
def add_ssh_access_sg(sg_id, ip_address):
  ip_address = f"{ip_address}/32"

  response = ec2_client.authorize_security_group_ingress(
    CidrIp=ip_address,
    FromPort=22,
    GroupId=sg_id,
    IpProtocol='tcp',
    ToPort=22,
  )
  if response.get("Return"):
    print("Rule added successfully")
  else:
    print("Rule was not added")
def add_http_access_sg(security_group_id):
  response = ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpProtocol='tcp',
        FromPort=80,
        ToPort=80,
        CidrIp='0.0.0.0/0'
    )
  if response.get("Return"):
    print("Rule added successfully")
  else:
    print("Rule was not added")
def run_ec2(sg_id, subnet_id, instance_name):
  response = ec2_client.run_instances(
    BlockDeviceMappings=[
      {
        "DeviceName": "/dev/sda1",
        "Ebs": {
          "DeleteOnTermination": True,
          "VolumeSize": 10,
          "VolumeType": "gp2",
          "Encrypted": False
        },
      },
    ],
    ImageId="ami-0261755bbcb8c4a84",
    InstanceType="t2.micro",
    KeyName=args.key_pair_name,
    MaxCount=1,
    MinCount=1,
    Monitoring={"Enabled": True},
    # SecurityGroupIds=[
    #     sg_id,
    # ],
    # SubnetId=subnet_id,
    UserData="""#!/bin/bash
echo "Hello I am from user data" > info.txt
""",
    InstanceInitiatedShutdownBehavior="stop",
    NetworkInterfaces=[
      {
        "AssociatePublicIpAddress": True,
        "DeleteOnTermination": True,
        "Groups": [
          sg_id,
        ],
        "DeviceIndex": 0,
        "SubnetId": subnet_id,
      },
    ],
  )

  for instance in response.get("Instances"):
    instance_id = instance.get("InstanceId")
    print("InstanceId - ", instance_id)
  # pprint(response)

  # Create a name tag for the instance
  tag = {'Key': 'Name', 'Value': instance_name}

  # Assign the name tag to the instance
  ec2_client.create_tags(Resources=[instance_id], Tags=[tag])

  return None
def create_ec2_with_VPC(vpc_id, subnet_id):
  my_ip = get_my_public_ip()
  create_key_pair(args.key_pair_name)
  security_group_id = create_security_group(
    "ec2-sg", "Security group to enable access on ec2", vpc_id)
  time.sleep(5)
  add_ssh_access_sg(security_group_id, my_ip)
  add_http_access_sg(security_group_id)
  run_ec2(security_group_id, subnet_id, 'btu-avto-instance')
if args.create_vpc:
  create_vpc()
if args.tag_vpc:
  add_name_tag(args.vpc_id)
if args.create_IGW:
  igw_id = create_igw()
  if args.attach_IGW:
    attach_igw_to_vpc(args.vpc_id, igw_id)
    print(f'internet gateway{igw_id} attached to vpc{args.vpc_id}')
if args.create_vpc_with_subnets:
  if args.npr + args.npu < 200:
    result = ec2_client.create_vpc(CidrBlock="10.22.0.0/16")
    vpc = result.get("Vpc")
    print(vpc)
    vpc = result.get("Vpc")
    vpc_id = vpc.get("VpcId")
    for i in range(args.npr):
      subnet_id = create_subnet(vpc_id, f'10.22.{i}.0/24', f'private_sub_{i}')
      time.sleep(2)
      rtb_id = create_route_table_without_route(vpc_id)
      time.sleep(2)
      associate_route_table_to_subnet(rtb_id, subnet_id)
      time.sleep(2)
    for i in range(args.npu):
      subnet_id = create_subnet(vpc_id, f'10.22.{i+args.npr}.0/24', f'public_sub_{i+args.npr}')
      time.sleep(2)
      rtb_id = create_route_table_with_route(vpc_id, 'my_route_name',
                                            create_or_get_igw(vpc_id))
      time.sleep(2)
      associate_route_table_to_subnet(rtb_id, subnet_id)
      time.sleep(2)
      enable_auto_public_ips(subnet_id, 'enable')
      time.sleep(2)
  else:
    print("subnet_ების რაოდენობა არ უნდა აღემატებოდეს 200")
if args.vpc_id and args.subnet_id:
  create_ec2_with_VPC(args.vpc_id, args.subnet_id)
  
