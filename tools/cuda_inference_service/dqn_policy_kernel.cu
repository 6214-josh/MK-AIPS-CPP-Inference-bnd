extern "C" __global__
void dqn_policy_kernel(const float* features, float* q_values) {
    // features:
    // 0 shortage_qty
    // 1 material_available_flag, 1=true, 0=false
    // 2 delay_risk_score
    // 3 quality_risk_score
    // 4 current_oee
    // 5 abnormal_power_flag, 1=true, 0=false
    // 6 machine_status_code: 0=NORMAL, 1=STOPPED, 2=ABNORMAL

    float shortage = features[0];
    float material_available = features[1];
    float delay_risk = features[2];
    float quality_risk = features[3];
    float oee = features[4];
    float abnormal_power = features[5];
    float machine_status = features[6];

    // 0 KEEP_CURRENT_SCHEDULE
    q_values[0] = 0.55f + (material_available * 0.20f) + ((1.0f - delay_risk) * 0.15f) + (oee * 0.10f);

    // 1 REQUEST_MATERIAL_REPLENISHMENT
    q_values[1] = 0.20f + (shortage * 0.12f) + ((1.0f - material_available) * 1.20f) + (delay_risk * 0.20f);

    // 2 INCREASE_ORDER_PRIORITY
    q_values[2] = 0.30f + (delay_risk * 1.10f) + (oee * 0.20f) - (shortage * 0.03f);

    // 3 REASSIGN_MACHINE
    q_values[3] = 0.25f + ((1.0f - oee) * 0.90f) + (delay_risk * 0.25f) + (machine_status * 0.15f);

    // 4 PAUSE_WORK_ORDER
    q_values[4] = 0.10f + (quality_risk * 0.80f) + (abnormal_power * 0.50f) + (machine_status * 0.20f);

    // 5 INSERT_URGENT_WORK_ORDER
    q_values[5] = 0.15f + (delay_risk * 0.70f) + (material_available * 0.20f) + (oee * 0.15f);

    // 6 MAINTENANCE_CHECK
    q_values[6] = 0.20f + (abnormal_power * 1.00f) + (quality_risk * 0.45f) + (machine_status * 0.40f) + ((1.0f - oee) * 0.25f);
}
