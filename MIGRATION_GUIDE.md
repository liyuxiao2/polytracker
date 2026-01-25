# PostgreSQL Migration Guide

This guide will help you migrate from SQLite to PostgreSQL for better scalability and performance.

## Why PostgreSQL?

- **Better concurrency**: Handle multiple simultaneous connections efficiently
- **Advanced indexing**: Superior performance for complex analytical queries
- **Scalability**: Better suited for production workloads with large datasets
- **Data integrity**: Strong ACID compliance and constraint enforcement
- **JSON support**: Native JSONB for flexible data structures

## Prerequisites

- Docker and Docker Compose installed
- Python 3.9+ with virtual environment
- Existing SQLite database (if migrating data)

## Migration Steps

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs `asyncpg` (PostgreSQL async driver) and `psycopg2-binary` (PostgreSQL adapter).

### 2. Start PostgreSQL with Docker Compose

```bash
# From the project root
docker-compose up -d postgres
```

This starts PostgreSQL on `localhost:5432` with:
- **Database**: `polytracker`
- **User**: `polytracker`
- **Password**: `polytracker_dev_password`

To verify it's running:
```bash
docker-compose ps
```

### 3. Update Environment Configuration

Create or update your `.env` file in the `backend/` directory:

```bash
cp .env.example .env
```

Ensure the `DATABASE_URL` is set to PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://polytracker:polytracker_dev_password@localhost:5432/polytracker
```

### 4. Migrate Your Data (Optional)

If you have existing data in SQLite that you want to keep:

```bash
cd backend
python migrate_to_postgres.py
```

The script will:
- Connect to both SQLite and PostgreSQL
- Create all tables in PostgreSQL
- Copy all data from SQLite to PostgreSQL
- Verify the migration was successful

**Note**: If starting fresh, skip this step. The tables will be created automatically when you start the application.

### 5. Verify the Migration

Start your application:

```bash
cd backend
python run.py
```

Check that:
- Application starts without errors
- Database tables are created
- Queries work correctly

### 6. Optional: Database Management UI

To use pgAdmin for database management:

```bash
docker-compose --profile tools up -d pgadmin
```

Access pgAdmin at `http://localhost:5050`:
- **Email**: `admin@polytracker.local`
- **Password**: `admin`

Add a new server in pgAdmin:
- **Host**: `postgres` (or `localhost` if accessing from your machine)
- **Port**: `5432`
- **Database**: `polytracker`
- **Username**: `polytracker`
- **Password**: `polytracker_dev_password`

## Configuration Options

### Connection Pooling

The default configuration in [database.py](backend/app/models/database.py#L13) uses:
- `pool_size=20`: Maximum number of persistent connections
- `max_overflow=10`: Additional connections allowed beyond pool_size
- `pool_pre_ping=True`: Verify connections before use
- `pool_recycle=3600`: Recycle connections after 1 hour

Adjust these based on your workload:

```python
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### Production Configuration

For production, use environment variables:

```env
# Production PostgreSQL (managed service)
DATABASE_URL=postgresql+asyncpg://user:password@db-host.region.provider.com:5432/polytracker
```

Consider using managed PostgreSQL services:
- **AWS RDS**: Managed PostgreSQL with automated backups
- **Render**: Easy deployment with PostgreSQL included
- **Supabase**: PostgreSQL with real-time capabilities
- **DigitalOcean**: Managed databases with good pricing

## Rollback to SQLite (If Needed)

If you need to rollback:

1. Update your `.env` file:
   ```env
   DATABASE_URL=sqlite+aiosqlite:///./polyedge.db
   ```

2. Restart your application

Note: SQLite is not recommended for production use.

## Backup and Maintenance

### PostgreSQL Backup

```bash
# Backup
docker exec polytracker-postgres pg_dump -U polytracker polytracker > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i polytracker-postgres psql -U polytracker polytracker < backup_20260124.sql
```

### Stop PostgreSQL

```bash
docker-compose down postgres
```

### Remove PostgreSQL Data (Danger!)

```bash
docker-compose down -v  # Removes all volumes including database data
```

## Performance Tips

1. **Indexes**: The application already defines indexes on frequently queried columns
2. **Connection pooling**: Configured automatically for optimal performance
3. **Query optimization**: Use EXPLAIN ANALYZE for slow queries
4. **Monitoring**: Consider pg_stat_statements extension for query monitoring

## Troubleshooting

### Connection Refused

```
Error: connection refused
```

**Solution**: Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
docker-compose logs postgres
```

### Authentication Failed

```
Error: password authentication failed
```

**Solution**: Verify credentials in `.env` match docker-compose.yml

### Migration Script Fails

```
Error during migration: [error message]
```

**Solution**:
- Ensure SQLite database exists at `./polyedge.db`
- Check PostgreSQL is running
- Verify you're in the `backend/` directory

### Port Already in Use

```
Error: port 5432 already in use
```

**Solution**: Stop other PostgreSQL instances or change the port in docker-compose.yml:
```yaml
ports:
  - "5433:5432"  # External:Internal
```

Then update your DATABASE_URL accordingly.

## Next Steps

After successful migration:

1. Monitor application performance
2. Set up automated backups
3. Consider PostgreSQL-specific optimizations
4. Update deployment configuration for production
5. Remove SQLite database after confirming everything works

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
