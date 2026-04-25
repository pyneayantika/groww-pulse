from pathlib import Path

dockerfile = Path('Dockerfile')
content = dockerfile.read_text(encoding='utf-8')
print('CURRENT Dockerfile:')
print(content)
print()

# Make the 3 changes needed for Fly.io
new_content = content

# Change 1: Add PORT env variable
if 'ENV PORT' not in new_content:
    new_content = new_content.replace(
        'WORKDIR /app',
        'WORKDIR /app\nENV PORT=8080'
    )

# Change 2: Expose correct port
if 'EXPOSE' not in new_content:
    new_content = new_content.replace(
        '# Default: run scheduler',
        'EXPOSE 8080\n\n# Default: run dashboard'
    )

# Change 3: Run dashboard not scheduler
new_content = new_content.replace(
    'CMD ["python", "scheduler/cron_runner.py"]',
    'CMD ["python", "dashboard/app.py"]'
)

dockerfile.write_text(new_content, encoding='utf-8')
print('UPDATED Dockerfile:')
print(new_content)
print()
print('Dockerfile updated for Fly.io')
