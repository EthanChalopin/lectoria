############################
# VPC + Subnets + Internet
############################

# On récupère les zones de disponibilité de la région (eu-west-1a, eu-west-1b, etc.)
data "aws_availability_zones" "available" {
  state = "available"
}

# VPC principal pour le projet Bookgen
resource "aws_vpc" "bookgen" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "bookgen-vpc"
  }
}

# Internet Gateway pour permettre l'accès à Internet depuis le VPC
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.bookgen.id

  tags = {
    Name = "bookgen-igw"
  }
}

# Route table publique (vers Internet via l'IGW)
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.bookgen.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "bookgen-public-rt"
  }
}

# Deux sous-réseaux publics dans 2 zones de dispo différentes
# Subnet 1 : 10.0.1.0/24
resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.bookgen.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[0]

  tags = {
    Name = "bookgen-public-a"
  }
}

# Subnet 2 : 10.0.2.0/24
resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.bookgen.id
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[1]

  tags = {
    Name = "bookgen-public-b"
  }
}

# On associe la route table publique aux deux subnets
resource "aws_route_table_association" "public_a_assoc" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b_assoc" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}


# --- PRIVATE SUBNETS (one per AZ) ---

resource "aws_subnet" "private_a" {
  vpc_id                  = aws_vpc.bookgen.id
  cidr_block              = "10.0.11.0/24"
  availability_zone       = "eu-west-1a"
  map_public_ip_on_launch = false

  tags = {
    Name = "bookgen-private-a"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id                  = aws_vpc.bookgen.id
  cidr_block              = "10.0.12.0/24"
  availability_zone       = "eu-west-1b"
  map_public_ip_on_launch = false

  tags = {
    Name = "bookgen-private-b"
  }
}

# --- NAT GATEWAY (1 per VPC for now) ---

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "bookgen-nat-eip"
  }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_a.id

  depends_on = [aws_internet_gateway.igw]

  tags = {
    Name = "bookgen-nat"
  }
}

# --- PRIVATE ROUTE TABLE ---

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.bookgen.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = {
    Name = "bookgen-private-rt"
  }
}

resource "aws_route_table_association" "private_a_assoc" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b_assoc" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}
