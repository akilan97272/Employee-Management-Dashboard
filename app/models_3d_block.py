from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Area(Base):
    __tablename__ = 'areas'
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True)
    buildings = relationship('Building', back_populates='area')

class Building(Base):
    __tablename__ = 'buildings'
    id = Column(Integer, primary_key=True)
    name = Column(String(120))
    area_id = Column(Integer, ForeignKey('areas.id'))
    floor_no = Column(String(20), nullable=True)
    glb_path = Column(String(512))
    max_limit_people = Column(Integer, nullable=False, default=20)
    area = relationship('Area', back_populates='buildings')
