from sqlalchemy.orm import Session
from typing import List, Optional
from models import Project, Participant, ParticipantStatus
from schemas import ProjectCreate, ProjectJoinRequest, ProjectResponse, ParticipantResponse
from datetime import datetime


class ProjectService:
    def create_project(self, db: Session, project_data: ProjectCreate) -> Project:
        """创建可信模型计算项目"""
        db_project = Project(
            name=project_data.name,
            description=project_data.description,
            owner_id=project_data.owner_id,
            data_config=project_data.data_config
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    def get_project(self, db: Session, project_id: int) -> Optional[Project]:
        """获取项目"""
        return db.query(Project).filter(Project.id == project_id).first()

    def list_projects(self, db: Session, skip: int = 0, limit: int = 100) -> List[Project]:
        """获取项目列表"""
        return db.query(Project).offset(skip).limit(limit).all()

    def join_project(self, db: Session, project_id: int, request: ProjectJoinRequest) -> Project:
        """加入项目（审批加入请求）"""
        project = self.get_project(db, project_id)
        if not project:
            raise ValueError("项目不存在")

        # 检查是否已经加入
        existing = db.query(Participant).filter(
            Participant.project_id == project_id,
            Participant.participant_id == request.participant_id
        ).first()

        if existing:
            if existing.status == ParticipantStatus.APPROVED:
                raise ValueError("已经加入该项目")
            # 更新请求
            existing.participant_name = request.participant_name
            existing.data_resource = request.data_resource
            existing.status = ParticipantStatus.APPROVED
            existing.joined_at = datetime.utcnow()
        else:
            # 创建新的参与者记录
            participant = Participant(
                project_id=project_id,
                participant_id=request.participant_id,
                participant_name=request.participant_name,
                data_resource=request.data_resource,
                status=ParticipantStatus.APPROVED,
                joined_at=datetime.utcnow()
            )
            db.add(participant)

        db.commit()
        db.refresh(project)
        return project

    def list_participants(self, db: Session, project_id: int) -> List[Participant]:
        """获取项目参与者列表"""
        return db.query(Participant).filter(
            Participant.project_id == project_id,
            Participant.status == ParticipantStatus.APPROVED
        ).all()
