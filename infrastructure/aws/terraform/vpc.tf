# Network layout, explained in full in docs/learning/PHASE_8_CLOUD_AWS.md:
#
# - Public subnets: the ALB and the Fargate tasks (backend, worker,
#   frontend) live here, each with a public IP, but are only actually
#   reachable per what their security group allows — the ALB from the
#   internet, everything else only from the ALB. This avoids a NAT
#   Gateway (~$32/month fixed cost) while Fargate tasks still need to
#   reach out to pull images from ECR and (for the worker) call an AI
#   provider or Ollama.
# - Private (isolated) subnets: RDS and ElastiCache live here, with no
#   route to the internet at all — a managed database has no reason to
#   ever initiate an outbound connection, so it doesn't need one.

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_subnet" "public" {
  count                   = var.availability_zone_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${count.index}"
  }
}

resource "aws_subnet" "private" {
  count             = var.availability_zone_count
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + var.availability_zone_count)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-private-${count.index}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = var.availability_zone_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private subnets deliberately get no route table entry to the internet —
# the default (local-VPC-only) implicit route is all RDS/ElastiCache need.
