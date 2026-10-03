-- 陪玩技能认证审核 MySQL 表设计。
-- 本项目运行时使用 SQLAlchemy/Alembic 管理实际数据库；这里给出 MySQL 等价建表语句，便于部署到 MySQL 时参考。

CREATE TABLE IF NOT EXISTS player_skills (
  id CHAR(36) PRIMARY KEY,
  player_id CHAR(36) NOT NULL,
  game_id CHAR(36) NOT NULL,
  rank VARCHAR(80) NULL,
  description TEXT NOT NULL,
  evidence_url VARCHAR(512) NULL COMMENT 'MinIO 图片访问地址',
  verification_status ENUM('PENDING', 'APPROVED', 'REJECTED', 'REVOKED') NOT NULL DEFAULT 'PENDING',
  review_note TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_player_skill_player_game (player_id, game_id),
  KEY ix_player_skills_player_id (player_id),
  KEY ix_player_skills_game_id (game_id),
  KEY ix_player_skills_verification_status (verification_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS player_skill_audit_logs (
  id CHAR(36) PRIMARY KEY,
  skill_id CHAR(36) NOT NULL,
  operator_user_id CHAR(36) NOT NULL,
  action ENUM('APPROVE', 'REJECT', 'REVOKE') NOT NULL,
  from_status VARCHAR(32) NOT NULL,
  to_status VARCHAR(32) NOT NULL,
  reason TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_player_skill_audit_logs_skill_id (skill_id),
  KEY ix_player_skill_audit_logs_operator_user_id (operator_user_id),
  KEY ix_player_skill_audit_logs_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
