-- Add optional company/package preferences and targeted notifications.
ALTER TABLE `student_profile`
  ADD COLUMN `preferred_company` VARCHAR(255) DEFAULT NULL;

ALTER TABLE `job_role`
  ADD COLUMN `salary_lpa_min` FLOAT DEFAULT NULL;

ALTER TABLE `notification`
  ADD COLUMN `target_user_id` INT DEFAULT NULL,
  ADD INDEX `idx_notification_target_user` (`target_user_id`),
  ADD CONSTRAINT `fk_notification_target_user`
    FOREIGN KEY (`target_user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE;
