#include <sys/time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <stdatomic.h>

#define RING_SIZE 1024
#define LOOKBACK 20
#define PREDICT_HORIZON 5
#define MAX_TICKS 100000

// ========== Existing Data Structures (YOUR CODE) ==========
typedef struct {
    long timestamp_us;
    double price;
    int volume;
    char side;
} Tick;

typedef struct {
    Tick* buffer;
    atomic_size_t head;
    atomic_size_t tail;
    size_t size_mask;
} RingBuffer;

typedef struct {
    double momentum;
    double volatility;
    double volume_imb;
    double trend;
    double rsi;
} Features;

// ========== Result Structure for Python ==========
// This is what gets returned to Python
typedef struct {
    double total_return;
    double accuracy;
    int predictions;
    int correct;
    double buy_hold;
    double alpha;
    double throughput;
    double elapsed_seconds;
    int total_bars;
    char error_message[256];
} AnalysisResult;

// ========== ALL YOUR EXISTING FUNCTIONS (Keep them exactly as is) ==========

RingBuffer* create_ringbuffer(size_t size) {
    if ((size & (size - 1)) != 0) return NULL;
    RingBuffer* rb = (RingBuffer*)malloc(sizeof(RingBuffer));
    rb->buffer = (Tick*)malloc(sizeof(Tick) * size);
    rb->size_mask = size - 1;
    atomic_init(&rb->head, 0);
    atomic_init(&rb->tail, 0);
    return rb;
}

void push_tick(RingBuffer* rb, Tick tick) {
    size_t head = atomic_load(&rb->head);
    size_t next_head = (head + 1) & rb->size_mask;
    size_t tail = atomic_load(&rb->tail);
    
    if (next_head != tail) {
        rb->buffer[head] = tick;
        atomic_store(&rb->head, next_head);
    }
}

int get_ticks(RingBuffer* rb, Tick* out_ticks, int max_count) {
    size_t tail = atomic_load(&rb->tail);
    size_t head = atomic_load(&rb->head);
    
    if (tail == head) return 0;
    
    int count = 0;
    while (tail != head && count < max_count) {
        out_ticks[count] = rb->buffer[tail];
        tail = (tail + 1) & rb->size_mask;
        count++;
    }
    return count;
}

int load_kaggle_data(const char* filename, Tick* out_ticks, int max_ticks) {
    FILE* file = fopen(filename, "r");
    if (!file) {
        return 0;
    }
    
    char line[512];
    int count = 0;
    
    fgets(line, sizeof(line), file);
    
    while (fgets(line, sizeof(line), file) && count < max_ticks) {
        char time_str[64];
        double open, high, low, close;
        int volume;
        
        if (sscanf(line, "%[^,],%lf,%lf,%lf,%lf,%d",
                   time_str, &open, &high, &low, &close, &volume) == 6) {
            
            struct tm tm = {0};
            strptime(time_str, "%Y-%m-%d %H:%M:%S", &tm);
            time_t seconds = mktime(&tm);
            
            out_ticks[count].timestamp_us = (long)seconds * 1000000LL;
            out_ticks[count].price = close;
            out_ticks[count].volume = volume;
            out_ticks[count].side = (close > open) ? 'B' : 'S';
            count++;
        }
    }
    
    fclose(file);
    return count;
}

Features extract_features(Tick* ticks, int count) {
    Features f = {0};
    if (count < 20) return f;
    
    double old_price = ticks[count - 6].price;
    double new_price = ticks[count - 1].price;
    f.momentum = (new_price - old_price) / old_price * 100;
    
    double returns[10];
    int ret_count = 0;
    for (int i = count - 10; i < count && i > 0; i++) {
        double ret = (ticks[i].price - ticks[i-1].price) / ticks[i-1].price;
        returns[ret_count++] = ret;
    }
    
    double mean = 0;
    for (int i = 0; i < ret_count; i++) mean += returns[i];
    mean /= ret_count;
    
    double variance = 0;
    for (int i = 0; i < ret_count; i++) {
        variance += (returns[i] - mean) * (returns[i] - mean);
    }
    variance /= ret_count;
    f.volatility = sqrt(variance) * 100;
    
    for (int i = count - 5; i < count && i > 0; i++) {
        double price_change = ticks[i].price - ticks[i-1].price;
        if (price_change > 0) {
            f.volume_imb += ticks[i].volume;
        } else if (price_change < 0) {
            f.volume_imb -= ticks[i].volume;
        }
    }
    f.volume_imb = f.volume_imb / 10000;
    
    int n = 10;
    double sum_x = 0, sum_y = 0, sum_xy = 0, sum_x2 = 0;
    for (int i = 0; i < n; i++) {
        int idx = count - n + i;
        double x = i;
        double y = ticks[idx].price;
        sum_x += x;
        sum_y += y;
        sum_xy += x * y;
        sum_x2 += x * x;
    }
    double slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x);
    f.trend = slope / ticks[count-1].price * 100;
    
    double gains = 0, losses = 0;
    int rsi_period = 14;
    for (int i = count - rsi_period; i < count && i > 0; i++) {
        double change = ticks[i].price - ticks[i-1].price;
        if (change > 0) gains += change;
        else losses -= change;
    }
    if (losses == 0) losses = 0.001;
    double rs = gains / losses;
    f.rsi = 100 - (100 / (1 + rs));
    f.rsi = (f.rsi - 50) / 50;
    
    return f;
}

double predict(Features f) {
    double score = f.momentum * 0.25 + f.volume_imb * 0.20 + 
                   f.trend * 0.30 + f.rsi * 0.15 - f.volatility * 0.10;
    
    if (score > 0.5) score = 0.5;
    if (score < -0.5) score = -0.5;
    
    return score;
}

// ========== NEW: Function that Python can call ==========
// This replaces main() and returns results as a struct

AnalysisResult* analyze_csv_file(const char* filename) {
    AnalysisResult* result = (AnalysisResult*)malloc(sizeof(AnalysisResult));
    memset(result, 0, sizeof(AnalysisResult));
    
    struct timeval start, end;
    gettimeofday(&start, NULL);
    
    Tick* ticks = (Tick*)malloc(sizeof(Tick) * MAX_TICKS);
    if (!ticks) {
        snprintf(result->error_message, sizeof(result->error_message), "Memory allocation failed");
        return result;
    }
    
    int tick_count = load_kaggle_data(filename, ticks, MAX_TICKS);
    
    if (tick_count == 0) {
        snprintf(result->error_message, sizeof(result->error_message), "No data loaded from file");
        free(ticks);
        return result;
    }
    
    result->total_bars = tick_count;
    
    // Run backtest
    int predictions = 0;
    int correct = 0;
    double total_return = 0;
    
    for (int i = LOOKBACK; i < tick_count - PREDICT_HORIZON - 5; i++) {
        Features f = extract_features(ticks + i - LOOKBACK, LOOKBACK);
        double pred = predict(f);
        
        int signal = 0;
        if (pred > 0.1) signal = 1;
        else if (pred < -0.1) signal = -1;
        
        if (signal != 0) {
            predictions++;
            
            double future_price = ticks[i + PREDICT_HORIZON].price;
            double current_price = ticks[i].price;
            double actual_return = (future_price - current_price) / current_price * 100;
            
            if ((signal == 1 && actual_return > 0) || (signal == -1 && actual_return < 0)) {
                correct++;
                total_return += fabs(actual_return);
            } else {
                total_return -= fabs(actual_return);
            }
        }
    }
    
    result->predictions = predictions;
    result->correct = correct;
    result->total_return = total_return;
    result->accuracy = (predictions > 0) ? (double)correct / predictions * 100 : 0;
    
    // Benchmark
    result->buy_hold = (ticks[tick_count-1].price - ticks[0].price) / ticks[0].price * 100;
    result->alpha = result->total_return - result->buy_hold;
    
    gettimeofday(&end, NULL);
    result->elapsed_seconds = (end.tv_sec - start.tv_sec) + 
                              (end.tv_usec - start.tv_usec) / 1000000.0;
    result->throughput = tick_count / result->elapsed_seconds;
    
    free(ticks);
    return result;
}

// ========== NEW: Free the result structure ==========
void free_analysis_result(AnalysisResult* result) {
    free(result);
}

// ========== Optional: Keep main() for command-line testing ==========
// Comment out main() when compiling as shared library, or use #ifdef

#ifdef STANDALONE
int main(int argc, char* argv[]) {
    if (argc < 2) {
        printf("Usage: %s <csv_file>\n", argv[0]);
        return 1;
    }
    
    AnalysisResult* result = analyze_csv_file(argv[1]);
    
    if (strlen(result->error_message) > 0) {
        printf("Error: %s\n", result->error_message);
    } else {
        printf("╔══════════════════════════════════════════════════════════╗\n");
        printf("║                    BACKTEST RESULTS                       ║\n");
        printf("╚══════════════════════════════════════════════════════════╝\n\n");
        printf("  Total Predictions:  %d\n", result->predictions);
        printf("  Correct:            %d (%.1f%%)\n", result->correct, result->accuracy);
        printf("  Total Return:       %+.2f%%\n", result->total_return);
        printf("  Buy & Hold Return:  %+.2f%%\n", result->buy_hold);
        printf("  Alpha:              %+.2f%%\n", result->alpha);
        printf("  Time elapsed:       %.3f seconds\n", result->elapsed_seconds);
        printf("  Throughput:         %.0f bars/sec\n", result->throughput);
    }
    
    free_analysis_result(result);
    return 0;
}
#endif