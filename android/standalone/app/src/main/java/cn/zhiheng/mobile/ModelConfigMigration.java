package cn.zhiheng.mobile;

/** A release migration only replaces a known bundled default, never another service. */
final class ModelConfigMigration {
    static final String LEESSMIN_MIGRATION = "model_migration_v9";
    static final String SOL_MIGRATION = "model_migration_v10_sol";

    static final class Config {
        final String raw, endpoint, model, vision, protocol;

        Config(String raw, String endpoint, String model, String vision, String protocol) {
            this.raw = raw;
            this.endpoint = normalized(endpoint).replaceAll("/+$", "");
            this.model = normalized(model);
            String visionValue = normalized(vision);
            this.vision = visionValue.isEmpty() ? this.model : visionValue;
            this.protocol = normalized(protocol);
        }
    }

    static String selectForLeessminRelease(Config saved, Config bundled, boolean alreadyMigrated) {
        if (alreadyMigrated || bundled == null || !isLeessminDefault(bundled) || !isLegacyDefault(saved)) {
            return saved == null ? null : saved.raw;
        }
        // Replace the complete envelope, including its credential. Reusing the
        // old service's credential with the new endpoint would break connectivity.
        return bundled.raw;
    }

    private static boolean isLeessminDefault(Config config) {
        return config.endpoint.equals("https://code.leessmin.com/v1")
            && config.model.equals("gpt-5.5") && config.vision.equals("gpt-5.5")
            && config.protocol.equals("chat_completions");
    }

    static String selectForSolRelease(Config saved, Config bundled, boolean alreadyMigrated) {
        if (alreadyMigrated || saved == null || bundled == null
            || !bundled.endpoint.equals("https://code.leessmin.com/v1")
            || !bundled.model.equals("gpt-6.1-sol") || !bundled.vision.equals("gpt-6.1-sol")
            || !bundled.protocol.equals("chat_completions")) return saved == null ? null : saved.raw;
        return isLeessminDefault(saved) || isLegacyDefault(saved) ? bundled.raw : saved.raw;
    }

    private static boolean isLegacyDefault(Config config) {
        if (config == null || !config.vision.equals(config.model)
            || !(config.protocol.isEmpty() || config.protocol.equals("auto")
                || config.protocol.equals("chat_completions"))) return false;
        return ((config.endpoint.equals("https://cc-vibe.com/v1")
                 || config.endpoint.equals("https://server.max-tabs.com/v1"))
                && config.model.equals("gpt-5.5"))
            || ((config.endpoint.equals("http://47.110.38.211:8080/v1")
                 || config.endpoint.equals("https://www.vibecd.cc/v1"))
                && config.model.equals("claude-opus-4-8"));
    }

    private static String normalized(String value) {
        return value == null ? "" : value.trim();
    }
}
