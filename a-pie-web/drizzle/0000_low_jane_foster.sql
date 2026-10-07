CREATE TABLE `study_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`token_hash` text NOT NULL,
	`age_range` text NOT NULL,
	`gender` text NOT NULL,
	`urban` text NOT NULL,
	`city` text,
	`consent_version` text NOT NULL,
	`study_mode` text NOT NULL,
	`catalog_hash` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_sessions_token` ON `study_sessions` (`token_hash`);--> statement-breakpoint
CREATE TABLE `study_points` (
	`id` text PRIMARY KEY NOT NULL,
	`label` text NOT NULL,
	`lat` real NOT NULL,
	`lon` real NOT NULL,
	`pano_id` text NOT NULL,
	`heading` real DEFAULT 0 NOT NULL,
	`pitch` real DEFAULT 0 NOT NULL,
	`cohort` text DEFAULT 'unverified' NOT NULL,
	`active` integer DEFAULT 1 NOT NULL,
	`metrics_json` text,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `study_settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `study_trials` (
	`id` text PRIMARY KEY NOT NULL,
	`session_id` text NOT NULL,
	`round` integer NOT NULL,
	`left_id` text NOT NULL,
	`right_id` text NOT NULL,
	`left_snapshot` text NOT NULL,
	`right_snapshot` text NOT NULL,
	`choice` text,
	`reasons_json` text,
	`duration_ms` integer,
	`view_json` text,
	`answered_at` text,
	FOREIGN KEY (`session_id`) REFERENCES `study_sessions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_trials_session_round` ON `study_trials` (`session_id`,`round`);--> statement-breakpoint
CREATE INDEX `idx_trials_answered` ON `study_trials` (`answered_at`);