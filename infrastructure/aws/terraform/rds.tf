resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${var.project_name}-db-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  multi_az = false # single-AZ: real production would set this true for automatic failover, at roughly double the cost — a demo-scale trade-off, not an oversight

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"

  # A demo deployment that's never actually run production traffic has no
  # final snapshot worth keeping — real usage should flip this to false and
  # set final_snapshot_identifier instead.
  skip_final_snapshot = true

  deletion_protection = false # same demo-vs-production reasoning as above

  tags = { Name = "${var.project_name}-db" }
}
