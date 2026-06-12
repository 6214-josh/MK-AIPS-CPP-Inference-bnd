extern "C" __global__
void dqn_policy_kernel(const float* features, float* q_values) {
    // FIX76：缺貨優先 DQN CUDA kernel
    // features:
    // 0 line_side_shortage_qty
    // 1 material_available_flag, 1=true, 0=false
    // 2 delay_risk_score
    // 3 quality_risk_score
    // 4 current_oee
    // 5 abnormal_power_flag, 1=true, 0=false
    // 6 machine_status_code: 0=NORMAL, 1=STOPPED, 2=ABNORMAL
    // 7 customer_shortage_risk_score
    // 8 due_date_remaining_hours
    // 9 avg_power_demand

    float shortage_qty = features[0];
    float material_available = features[1];
    float delay_risk = features[2];
    float quality_risk = features[3];
    float oee = features[4];
    float abnormal_power = features[5];
    float machine_status = features[6];
    float customer_shortage = features[7];
    float due_hours = features[8];
    float avg_power = features[9];

    float line_shortage = (material_available < 0.5f || shortage_qty > 0.01f) ? 1.0f : 0.0f;
    float due_pressure = 1.0f - (due_hours / 72.0f);
    if (due_pressure < 0.0f) due_pressure = 0.0f;
    if (due_pressure > 1.0f) due_pressure = 1.0f;

    float energy_risk = avg_power / 15.0f;
    if (energy_risk > 1.0f) energy_risk = 1.0f;

    // 0 KEEP_CURRENT_SCHEDULE
    q_values[0] = 0.45f + material_available * 0.20f + (1.0f - delay_risk) * 0.12f + oee * 0.10f - customer_shortage * 2.20f;

    // 1 REQUEST_MATERIAL_REPLENISHMENT
    q_values[1] = 0.20f + line_shortage * 5.00f + customer_shortage * 2.20f + due_pressure * 0.60f;

    // 2 INCREASE_ORDER_PRIORITY
    q_values[2] = 0.30f + customer_shortage * 4.80f + delay_risk * 1.20f + due_pressure * 1.80f;

    // 3 REASSIGN_MACHINE
    q_values[3] = 0.25f + (1.0f - oee) * 0.90f + delay_risk * 0.30f + machine_status * 0.20f;

    // 4 PAUSE_LOW_PRIORITY_ORDER
    q_values[4] = 0.15f + (1.0f - customer_shortage) * 0.40f - due_pressure * 1.20f - customer_shortage * 4.00f;

    // 5 MAINTENANCE_CHECK
    q_values[5] = 0.20f + abnormal_power * 1.00f + quality_risk * 0.70f + machine_status * 0.40f - customer_shortage * 0.60f;

    // 6 OVERTIME_PRODUCTION
    q_values[6] = 0.25f + customer_shortage * 3.60f + due_pressure * 1.80f + delay_risk * 0.70f;

    // 7 ADJUST_BATCH_SIZE
    q_values[7] = 0.22f + customer_shortage * 1.80f + line_shortage * 0.80f + due_pressure * 0.40f - energy_risk * 0.20f;
}



extern "C" __global__
void reward_score_kernel(const float* features, float* reward_values) {
    // features:
    // 0 actual_oee
    // 1 delay_hours
    // 2 shortage_occurred_flag, 1=true, 0=false
    // 3 actual_yield_rate
    // 4 energy_kwh
    // 5 planned_processing_time
    // 6 machine_down_occurred_flag, 1=true, 0=false
    // 7 expected_oee_improvement_rate

    float actual_oee = features[0];
    float delay_hours = features[1];
    float shortage_occurred = features[2];
    float yield_rate = features[3];
    float energy_kwh = features[4];
    float planned = features[5];
    float machine_down = features[6];
    float expected_oee_improve = features[7];

    if (actual_oee < 0.0f) actual_oee = 0.0f;
    if (actual_oee > 1.0f) actual_oee = 1.0f;
    if (yield_rate < 0.0f) yield_rate = 0.0f;
    if (yield_rate > 1.0f) yield_rate = 1.0f;
    if (planned < 0.5f) planned = 0.5f;
    if (delay_hours < 0.0f) delay_hours = 0.0f;
    if (energy_kwh < 0.0f) energy_kwh = 0.0f;

    // Demo reward formula, 0~100:
    // Same business meaning as Python reward_service:
    // OEE + delivery + shortage + quality + energy, plus small CUDA-only expected OEE bonus.
    float reward_oee = actual_oee * 35.0f + fminf(fmaxf(expected_oee_improve, 0.0f), 0.2f) * 5.0f;
    float reward_delivery = fmaxf(0.0f, 20.0f - delay_hours * 2.0f);
    float reward_shortage = shortage_occurred > 0.5f ? 8.0f : 18.0f;
    if (machine_down > 0.5f) {
        reward_delivery = fmaxf(0.0f, reward_delivery - 4.0f);
        reward_shortage = fmaxf(0.0f, reward_shortage - 2.0f);
    }
    float reward_quality = yield_rate * 20.0f;
    float energy_ratio = 1.0f - fmaxf(0.0f, energy_kwh - planned * 6.0f) / fmaxf(planned * 8.0f, 1.0f);
    energy_ratio = fminf(fmaxf(energy_ratio, 0.0f), 1.0f);
    float reward_energy = energy_ratio * 7.0f;

    float total = reward_oee + reward_delivery + reward_shortage + reward_quality + reward_energy;
    total = fminf(98.0f, fmaxf(55.0f, total));

    // output:
    // 0 oee, 1 delivery, 2 shortage, 3 quality, 4 energy, 5 total
    reward_values[0] = reward_oee;
    reward_values[1] = reward_delivery;
    reward_values[2] = reward_shortage;
    reward_values[3] = reward_quality;
    reward_values[4] = reward_energy;
    reward_values[5] = total;
}
