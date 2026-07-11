# Engineering Development Process

## Sprint Cycle
We operate on 2-week sprints starting every other Monday.

### Sprint Schedule
- **Monday**: Sprint planning (2 hours)
- **Daily**: Standups at 10 AM (15 minutes)
- **Wednesday**: Mid-sprint check-in
- **Friday**: Demo and retrospective

## Code Review Requirements
All code must be reviewed by at least one senior engineer before merging.

### Review Checklist
- [ ] Code follows style guidelines
- [ ] Tests included and passing
- [ ] Documentation updated
- [ ] Security considerations addressed
- [ ] Performance impact assessed

## Deployment Pipeline
1. Feature branch created from main
2. Development on local environment
3. PR submitted with description
4. Automated tests run (CI)
5. Code review approval
6. Merge to staging
7. QA validation
8. Production deployment

## On-Call Rotation
Engineers rotate on-call responsibilities weekly. Primary on-call responds to alerts within 15 minutes.

## Tech Stack
- Backend: Python, Go
- Frontend: React, TypeScript
- Database: PostgreSQL, Redis
- Infrastructure: AWS, Kubernetes, Terraform
