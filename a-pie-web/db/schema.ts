import { integer, real, sqliteTable, text, uniqueIndex, index } from "drizzle-orm/sqlite-core";
export const points = sqliteTable("study_points", {
  id: text("id").primaryKey(), label: text("label").notNull(), lat: real("lat").notNull(), lon: real("lon").notNull(),
  panoId: text("pano_id").notNull(), heading: real("heading").notNull().default(0), pitch: real("pitch").notNull().default(0),
  cohort: text("cohort").notNull().default("unverified"), active: integer("active").notNull().default(1),
  metricsJson: text("metrics_json"), updatedAt: text("updated_at").notNull(),
});
export const participants = sqliteTable("study_sessions", {
  id: text("id").primaryKey(), tokenHash: text("token_hash").notNull(), ageRange: text("age_range").notNull(),
  gender: text("gender").notNull(), urban: text("urban").notNull(), city: text("city"),
  consentVersion: text("consent_version").notNull(), studyMode: text("study_mode").notNull(),
  catalogHash: text("catalog_hash").notNull(), createdAt: text("created_at").notNull(),
}, (t)=>[uniqueIndex("idx_sessions_token").on(t.tokenHash)]);
export const trials = sqliteTable("study_trials", {
  id: text("id").primaryKey(), sessionId: text("session_id").notNull().references(()=>participants.id),
  round: integer("round").notNull(), leftId: text("left_id").notNull(), rightId: text("right_id").notNull(),
  leftSnapshot: text("left_snapshot").notNull(), rightSnapshot: text("right_snapshot").notNull(),
  choice: text("choice"), reasonsJson: text("reasons_json"), durationMs: integer("duration_ms"),
  viewJson: text("view_json"), answeredAt: text("answered_at"),
}, (t)=>[uniqueIndex("idx_trials_session_round").on(t.sessionId,t.round), index("idx_trials_answered").on(t.answeredAt)]);
export const settings = sqliteTable("study_settings", {key:text("key").primaryKey(), value:text("value").notNull()});
