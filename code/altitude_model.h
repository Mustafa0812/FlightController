/* Auto-generated TinyML Altitude Estimator */
/* Target: STM32, ESP32, Teensy, Cortex-M microcontrollers */
#ifndef ALTITUDE_MODEL_H
#define ALTITUDE_MODEL_H

#include <math.h>

#define MODEL_NUM_INPUTS 5
#define MODEL_HIDDEN1    16
#define MODEL_HIDDEN2    8
#define DEFAULT_LPF_ALPHA 0.25f

/* Normalization Parameters */
static const float MEAN_X[5] = {-9.7326946e+00f, -4.5237136e-03f, -1.7770252e-03f, 7.2915689e-04f, 8.6005509e-01f};
static const float STD_X[5]  = {1.3707737e+00f, 9.8035961e-02f, 5.3909060e-02f, 2.6757792e-02f, 6.7628986e-01f};

/* Layer 1 (Linear + ReLU) */
static const float W0[16][5] = {
    {3.6777353e-01f, 1.5400000e-01f, -1.7286602e-01f, -4.4694763e-01f, -4.0303171e-01f},
    {-2.5396988e-01f, 2.3644024e-01f, -3.4561461e-01f, 2.6593578e-01f, 5.1513690e-01f},
    {4.2824548e-01f, -8.0888070e-02f, -2.6302108e-01f, 2.4993205e-01f, 1.5889539e-01f},
    {3.8024753e-01f, 2.6388505e-01f, -2.1880576e-01f, -2.2884445e-02f, 3.7559569e-01f},
    {-2.6393259e-01f, 3.9462391e-01f, 3.7447181e-01f, 3.3599535e-01f, 2.4920404e-01f},
    {3.2575220e-02f, 2.9548991e-01f, 1.4303438e-01f, -1.7325439e-01f, -6.7473292e-02f},
    {-1.7890939e-01f, 1.2872723e-01f, -6.6658854e-02f, 1.2056970e-01f, 1.9581746e-01f},
    {-5.3880864e-01f, -3.5981002e-01f, 3.8080853e-01f, -3.3915974e-02f, -1.2713547e-01f},
    {3.5538800e-02f, -2.2174150e-02f, 3.2880977e-01f, 3.6289018e-01f, 4.6267921e-01f},
    {4.3559458e-02f, 1.8031073e-01f, 1.1515044e-01f, 2.0612642e-01f, 6.1697885e-02f},
    {3.6269030e-01f, -4.5821095e-01f, 1.9966546e-01f, 3.0512912e-02f, 3.6290166e-01f},
    {1.3073495e-01f, 2.7966490e-01f, 4.3869793e-01f, 2.1936458e-01f, -4.4592217e-01f},
    {-5.3015316e-01f, -5.2348608e-01f, -1.2679109e-02f, -3.3455396e-01f, 2.1239518e-01f},
    {2.6251677e-01f, -5.1655346e-01f, 4.0255591e-02f, -5.0506175e-01f, -3.5007468e-01f},
    {-1.0265949e-01f, 2.0929575e-01f, -9.2066936e-02f, -2.3695076e-01f, 6.1448938e-01f},
    {-2.7707037e-01f, -3.3440241e-01f, -8.6725559e-03f, 3.1976274e-01f, -1.6358940e-01f}
};
static const float B0[16] = {-1.7908962e-01f, -9.6531436e-02f, -1.6564657e-01f, 5.2391553e-01f, 2.3834820e-01f, -2.3197666e-01f, -3.2254654e-01f, -4.5002654e-01f, -3.9368927e-01f, -4.5784679e-01f, 4.3299595e-01f, 3.7106425e-02f, 2.0629555e-01f, 4.9433623e-02f, 9.3783617e-02f, -5.3837943e-01f};

/* Layer 2 (Linear + ReLU) */
static const float W2[8][16] = {
    {-1.0745009e-01f, 2.9102728e-01f, -1.5103422e-01f, 3.2021081e-01f, 8.4697716e-02f, 8.7524980e-02f, -2.1891968e-01f, -8.0598789e-01f, 2.2019890e-01f, 6.7239716e-03f, 4.9213022e-02f, -3.7979748e-02f, 7.6194525e-02f, -2.5715137e-01f, 1.5390983e-02f, -1.0241471e-01f},
    {-2.1933505e-01f, 2.0770927e-01f, -1.2419589e-01f, 1.8065965e-01f, 2.2375783e-01f, 3.2078594e-01f, -1.4946592e-01f, 2.4133876e-01f, 1.5811537e-01f, 1.3626029e-01f, 3.9374506e-01f, -1.6418603e-01f, 3.4440872e-01f, -2.1135734e-01f, 2.0984927e-01f, 6.8000006e-04f},
    {-2.7567139e-01f, -1.2084302e-02f, -2.3920964e-01f, 3.3159417e-01f, -1.3089597e-02f, 1.0075789e-01f, -1.7334077e-01f, -3.0734376e-03f, 4.2757340e-02f, 2.3222214e-01f, 4.1193119e-01f, -1.9551839e-01f, 9.3581527e-02f, -4.3966758e-01f, 1.0999089e-01f, -5.4220922e-02f},
    {2.4765958e-01f, -1.1708755e-01f, -2.0407729e-01f, -1.0258410e-01f, -1.3949636e-01f, 1.7163816e-01f, 8.8199586e-06f, 5.3816877e-02f, -3.4122676e-01f, -3.2457535e-04f, 2.0406055e-01f, -3.0788410e-01f, -5.6535345e-01f, 3.9299697e-01f, -7.0600875e-02f, -3.5196331e-01f},
    {-5.6421861e-02f, 2.1507044e-01f, -3.1199035e-01f, 1.6579801e-01f, -8.1249051e-02f, 7.0026643e-03f, -1.1101674e-02f, 5.5550329e-02f, 7.4330710e-02f, 2.4331924e-01f, 1.4889868e-01f, -1.1811619e-01f, 1.6680449e-01f, -7.8722842e-02f, -5.3072959e-04f, -2.8888714e-01f},
    {-8.6417276e-06f, -5.1148649e-02f, -5.5806663e-02f, 5.9206739e-02f, 6.7936294e-02f, -6.6080667e-02f, -5.7006544e-03f, -7.4118176e-03f, -1.8082611e-02f, -3.4850657e-02f, 1.7613867e-02f, -4.6691801e-02f, -2.3937853e-02f, -2.4504529e-02f, -2.5237773e-02f, 9.3405199e-04f},
    {3.7590113e-02f, -1.3470100e-01f, 9.1619983e-02f, -1.1106598e-01f, -1.6576234e-01f, -1.1049489e-02f, -8.4042460e-02f, 9.7066179e-02f, 1.7286411e-01f, 2.5644032e-03f, 2.6661521e-02f, 1.1678959e-01f, 3.8614142e-01f, -1.1785982e-01f, -5.4967016e-01f, 6.3937598e-01f},
    {-2.9319674e-01f, 9.5084958e-02f, 9.9015273e-02f, 2.9954630e-01f, 1.9741082e-01f, -1.7979823e-02f, -3.3354960e-02f, -2.1762793e-01f, 6.0220048e-02f, -9.9498266e-03f, 1.0354406e-01f, -2.8541446e-01f, 3.5731217e-01f, -1.3393275e-01f, 1.6027850e-01f, -2.6574767e-01f}
};
static const float B2[8] = {2.1596169e-01f, 2.4729311e-01f, 3.9611053e-01f, -5.9148114e-02f, 4.4567293e-01f, -2.0209883e-01f, -5.2204615e-01f, 4.4601738e-01f};

/* Layer 3 (Output Linear) */
static const float W4[8] = {2.3662014e-01f, 3.4161347e-01f, 2.3996101e-01f, 4.5629328e-01f, 1.8755472e-01f, 1.9175079e-02f, -4.2671305e-01f, 3.5855347e-01f};
static const float B4 = -3.3395842e-02f;

/* Stateful Low-Pass / Exponential Moving Average (EMA) Filter */
typedef struct {
    float alpha;
    float current_val;
    int initialized;
} AltitudeLPF;

static inline void altitude_lpf_init(AltitudeLPF *lpf, float alpha) {
    lpf->alpha = alpha;
    lpf->current_val = 0.0f;
    lpf->initialized = 0;
}

static inline float altitude_lpf_update(AltitudeLPF *lpf, float raw_val) {
    if (!lpf->initialized) {
        lpf->current_val = raw_val;
        lpf->initialized = 1;
    } else {
        lpf->current_val = lpf->alpha * raw_val + (1.0f - lpf->alpha) * lpf->current_val;
    }
    return lpf->current_val;
}

/**
 * Predict vertical altitude with physical boundary clamping (>= 0.0 m).
 * Inputs (raw):
 *   in_features[0] = a_z (sensor_combined.accelerometer_m_s2[2])
 *   in_features[1] = omega_x (sensor_combined.gyro_rad[0])
 *   in_features[2] = omega_y (sensor_combined.gyro_rad[1])
 *   in_features[3] = omega_z (sensor_combined.gyro_rad[2])
 *   in_features[4] = baro_relative (current_baro_alt - takeoff_baro_alt)
 * 
 * Returns: Clamped altitude / distance to ground in meters (>= 0.0m).
 */
static inline float predict_altitude_raw(const float in_features[MODEL_NUM_INPUTS]) {
    float norm_x[MODEL_NUM_INPUTS];
    for (int i = 0; i < MODEL_NUM_INPUTS; i++) {
        norm_x[i] = (in_features[i] - MEAN_X[i]) / STD_X[i];
    }

    /* Hidden Layer 1 */
    float h1[MODEL_HIDDEN1];
    for (int i = 0; i < MODEL_HIDDEN1; i++) {
        float sum = B0[i];
        for (int j = 0; j < MODEL_NUM_INPUTS; j++) {
            sum += W0[i][j] * norm_x[j];
        }
        h1[i] = (sum > 0.0f) ? sum : 0.0f; /* ReLU */
    }

    /* Hidden Layer 2 */
    float h2[MODEL_HIDDEN2];
    for (int i = 0; i < MODEL_HIDDEN2; i++) {
        float sum = B2[i];
        for (int j = 0; j < MODEL_HIDDEN1; j++) {
            sum += W2[i][j] * h1[j];
        }
        h2[i] = (sum > 0.0f) ? sum : 0.0f; /* ReLU */
    }

    /* Output Layer */
    float out = B4;
    for (int j = 0; j < MODEL_HIDDEN2; j++) {
        out += W4[j] * h2[j];
    }

    /* Physical Boundary Clamping: Height above ground cannot be negative */
    if (out < 0.0f) {
        out = 0.0f;
    }

    return out;
}

/**
 * Predict altitude and filter through the EMA Low-Pass Filter in one step.
 */
static inline float predict_altitude_filtered(const float in_features[MODEL_NUM_INPUTS], AltitudeLPF *lpf) {
    float raw_pred = predict_altitude_raw(in_features);
    return altitude_lpf_update(lpf, raw_pred);
}

#endif /* ALTITUDE_MODEL_H */