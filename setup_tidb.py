import pymysql, os, sys
from dotenv import load_dotenv
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

host     = os.getenv("DB_HOST")
port     = int(os.getenv("DB_PORT", "4000"))
user     = os.getenv("DB_USER")
password = os.getenv("DB_PASS")
db_name  = os.getenv("DB_NAME", "program_navigator")

# DB 없이 먼저 연결해서 database 생성
conn = pymysql.connect(host=host, port=port, user=user, password=password,
                       charset='utf8mb4', ssl={})
with conn.cursor() as cur:
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"DB '{db_name}' 생성 완료")
conn.close()

# program_navigator에 연결
conn = pymysql.connect(host=host, port=port, user=user, password=password,
                       database=db_name, charset='utf8mb4', ssl={})

TABLES = [
    ("users", """
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email_verified_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("department", """
CREATE TABLE IF NOT EXISTS `department` (
  `department_id` bigint NOT NULL AUTO_INCREMENT,
  `college` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("major", """
CREATE TABLE IF NOT EXISTS `major` (
  `major_id` bigint NOT NULL AUTO_INCREMENT,
  `department_id` bigint NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`major_id`),
  KEY `fk_major_department` (`department_id`),
  CONSTRAINT `fk_major_department` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("competency", """
CREATE TABLE IF NOT EXISTS `competency` (
  `competency_id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`competency_id`),
  UNIQUE KEY `uk_competency_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("tag", """
CREATE TABLE IF NOT EXISTS `tag` (
  `tag_id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`tag_id`),
  UNIQUE KEY `uk_tag_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program", """
CREATE TABLE IF NOT EXISTS `program` (
  `program_id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description_html` mediumtext COLLATE utf8mb4_unicode_ci,
  `description_text` mediumtext COLLATE utf8mb4_unicode_ci,
  `thumbnail_data` mediumblob,
  `thumbnail_mime` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `organization` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `manager_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `manager_contact` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `recruit_start` date DEFAULT NULL,
  `recruit_end` date DEFAULT NULL,
  `edu_start` date DEFAULT NULL,
  `edu_end` date DEFAULT NULL,
  `location` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `capacity` int NOT NULL DEFAULT '0',
  `applicant_count` int NOT NULL DEFAULT '0',
  `waitlist_count` int NOT NULL DEFAULT '0',
  `mileage` int NOT NULL DEFAULT '0',
  `view_count` int NOT NULL DEFAULT '0',
  `enc_seq` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `review_summary` text COLLATE utf8mb4_unicode_ci,
  `review_summary_updated_at` datetime DEFAULT NULL,
  `embedding` json DEFAULT NULL,
  `raw_data` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`program_id`),
  KEY `idx_program_recruit_end` (`recruit_end`),
  KEY `idx_program_category` (`category`),
  KEY `idx_program_enc_seq` (`enc_seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_schedule", """
CREATE TABLE IF NOT EXISTS `program_schedule` (
  `schedule_id` bigint NOT NULL AUTO_INCREMENT,
  `program_id` bigint NOT NULL,
  `session_date` date NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  PRIMARY KEY (`schedule_id`),
  KEY `idx_schedule_program_date` (`program_id`,`session_date`),
  KEY `idx_schedule_date` (`session_date`),
  CONSTRAINT `fk_schedule_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_image", """
CREATE TABLE IF NOT EXISTS `program_image` (
  `image_id` bigint NOT NULL AUTO_INCREMENT,
  `program_id` bigint NOT NULL,
  `image_type` varchar(20) NOT NULL,
  `sort_order` int DEFAULT '0',
  `mime_type` varchar(50) DEFAULT NULL,
  `image_data` mediumblob NOT NULL,
  PRIMARY KEY (`image_id`),
  KEY `program_id` (`program_id`),
  CONSTRAINT `program_image_ibfk_1` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_file", """
CREATE TABLE IF NOT EXISTS `program_file` (
  `file_id` bigint NOT NULL AUTO_INCREMENT,
  `program_id` bigint NOT NULL,
  `file_name` varchar(255) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL,
  `file_data` mediumblob NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `chunk_index` int NOT NULL DEFAULT 0,
  `total_chunks` int NOT NULL DEFAULT 1,
  PRIMARY KEY (`file_id`),
  KEY `fk_pf_program` (`program_id`),
  CONSTRAINT `fk_pf_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_tag", """
CREATE TABLE IF NOT EXISTS `program_tag` (
  `program_id` bigint NOT NULL,
  `tag_id` bigint NOT NULL,
  `confidence` float DEFAULT NULL,
  `source` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'manual',
  PRIMARY KEY (`program_id`,`tag_id`),
  KEY `idx_ptag_tag` (`tag_id`),
  CONSTRAINT `fk_ptag_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ptag_tag` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`tag_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_competency", """
CREATE TABLE IF NOT EXISTS `program_competency` (
  `program_id` bigint NOT NULL,
  `competency_id` bigint NOT NULL,
  `weight` tinyint unsigned NOT NULL,
  PRIMARY KEY (`program_id`,`competency_id`),
  KEY `idx_pcomp_competency` (`competency_id`),
  CONSTRAINT `fk_pcomp_competency` FOREIGN KEY (`competency_id`) REFERENCES `competency` (`competency_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_pcomp_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("user_profile", """
CREATE TABLE IF NOT EXISTS `user_profile` (
  `user_id` bigint NOT NULL,
  `student_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `profile_image_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `grade` tinyint DEFAULT NULL,
  `department_id` bigint NOT NULL,
  `major_id` bigint DEFAULT NULL,
  `career_goal` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uk_profile_student_id` (`student_id`),
  KEY `fk_profile_department` (`department_id`),
  KEY `fk_profile_major` (`major_id`),
  CONSTRAINT `fk_profile_department` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `fk_profile_major` FOREIGN KEY (`major_id`) REFERENCES `major` (`major_id`),
  CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("refresh_token", """
CREATE TABLE IF NOT EXISTS `refresh_token` (
  `token_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `token_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime NOT NULL,
  PRIMARY KEY (`token_id`),
  KEY `idx_refresh_user` (`user_id`),
  KEY `idx_refresh_expires` (`expires_at`),
  CONSTRAINT `fk_refresh_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("review", """
CREATE TABLE IF NOT EXISTS `review` (
  `review_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `program_id` bigint NOT NULL,
  `rating` tinyint NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `uk_review_user_program` (`user_id`,`program_id`),
  KEY `idx_review_program` (`program_id`),
  CONSTRAINT `fk_review_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_review_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("recommendation", """
CREATE TABLE IF NOT EXISTS `recommendation` (
  `rec_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `program_id` bigint NOT NULL,
  `score` float NOT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`rec_id`),
  KEY `idx_rec_user_created` (`user_id`,`created_at`),
  KEY `idx_rec_program` (`program_id`),
  CONSTRAINT `fk_rec_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rec_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("timetable_slot", """
CREATE TABLE IF NOT EXISTS `timetable_slot` (
  `slot_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `semester` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `day_of_week` tinyint NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `course_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`slot_id`),
  KEY `idx_slot_user_semester` (`user_id`,`semester`),
  CONSTRAINT `fk_slot_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("user_interest", """
CREATE TABLE IF NOT EXISTS `user_interest` (
  `user_id` bigint NOT NULL,
  `tag_id` bigint NOT NULL,
  PRIMARY KEY (`user_id`,`tag_id`),
  KEY `idx_interest_tag` (`tag_id`),
  CONSTRAINT `fk_interest_profile` FOREIGN KEY (`user_id`) REFERENCES `user_profile` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_interest_tag` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`tag_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("user_preference", """
CREATE TABLE IF NOT EXISTS `user_preference` (
  `user_id` bigint NOT NULL,
  `ai_summary` text COLLATE utf8mb4_unicode_ci,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_pref_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("user_program", """
CREATE TABLE IF NOT EXISTS `user_program` (
  `user_id` bigint NOT NULL,
  `program_id` bigint NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`program_id`),
  KEY `idx_uprogram_program` (`program_id`),
  CONSTRAINT `fk_uprogram_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_uprogram_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("user_program_view", """
CREATE TABLE IF NOT EXISTS `user_program_view` (
  `user_id` bigint NOT NULL,
  `program_id` bigint NOT NULL,
  `view_count` int NOT NULL DEFAULT '1',
  `last_viewed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`program_id`),
  KEY `idx_upv_user_recent` (`user_id`,`last_viewed_at`),
  KEY `fk_upv_program` (`program_id`),
  CONSTRAINT `fk_upv_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_upv_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("program_application", """
CREATE TABLE IF NOT EXISTS `program_application` (
  `application_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `program_id` bigint NOT NULL,
  `status` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `cancelled_at` datetime DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`application_id`),
  UNIQUE KEY `uk_application_user_program` (`user_id`,`program_id`),
  KEY `idx_application_queue` (`program_id`,`status`,`applied_at`),
  CONSTRAINT `fk_application_program` FOREIGN KEY (`program_id`) REFERENCES `program` (`program_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_application_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("email_verification", """
CREATE TABLE IF NOT EXISTS `email_verification` (
  `verification_id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `code` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `purpose` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime NOT NULL,
  `verified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`verification_id`),
  KEY `idx_emailver_user` (`user_id`),
  CONSTRAINT `fk_emailver_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
    ("review_like", """
CREATE TABLE IF NOT EXISTS `review_like` (
  `user_id` bigint NOT NULL,
  `review_id` bigint NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`review_id`),
  KEY `idx_rlike_review` (`review_id`),
  CONSTRAINT `fk_rlike_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rlike_review` FOREIGN KEY (`review_id`) REFERENCES `review` (`review_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""),
]

with conn.cursor() as cur:
    for name, sql in TABLES:
        try:
            cur.execute(sql)
            conn.commit()
            print(f"  테이블 생성: {name}")
        except Exception as e:
            print(f"  오류 ({name}): {e}")

# 기존 DB 마이그레이션: 새 컬럼 추가 (이미 존재하면 무시)
MIGRATIONS = [
    ("user_profile에 nickname 추가",
     "ALTER TABLE `user_profile` ADD COLUMN `nickname` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `student_id`"),
    ("user_profile에 profile_image_url 추가",
     "ALTER TABLE `user_profile` ADD COLUMN `profile_image_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `nickname`"),
    ("review에 like_count 추가",
     "ALTER TABLE `review` ADD COLUMN `like_count` int NOT NULL DEFAULT 0 AFTER `content`"),
    ("program에 survey_url 추가",
     "ALTER TABLE `program` ADD COLUMN `survey_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `review_summary_updated_at`"),
    ("program.edu_start를 datetime으로 변경",
     "ALTER TABLE `program` MODIFY COLUMN `edu_start` datetime DEFAULT NULL"),
    ("program.edu_end를 datetime으로 변경",
     "ALTER TABLE `program` MODIFY COLUMN `edu_end` datetime DEFAULT NULL"),
    ("program.recruit_start를 datetime으로 변경",
     "ALTER TABLE `program` MODIFY COLUMN `recruit_start` datetime DEFAULT NULL"),
    ("program.recruit_end를 datetime으로 변경",
     "ALTER TABLE `program` MODIFY COLUMN `recruit_end` datetime DEFAULT NULL"),
]

with conn.cursor() as cur:
    for desc, sql in MIGRATIONS:
        try:
            cur.execute(sql)
            conn.commit()
            print(f"  마이그레이션 완료: {desc}")
        except Exception as e:
            if "Duplicate column name" in str(e) or "already exists" in str(e).lower():
                print(f"  마이그레이션 스킵 (이미 존재): {desc}")
            else:
                print(f"  마이그레이션 오류 ({desc}): {e}")

conn.close()
print("\n완료!")
