package org.lunardrift.wallpaper;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.SurfaceHolder;
import android.hardware.SensorManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import java.util.Timer;
import java.util.TimerTask;

public class LunarDriftWallpaper implements SensorEventListener {
    private SurfaceHolder surfaceHolder;
    private Context context;
    private Timer renderTimer;
    private boolean isRendering = false;
    private float gyroX = 0, gyroY = 0, gyroZ = 0;
    private float rotation = 0;
    private float tilt = 0;
    private float pulse = 1.0f;
    private long lastUpdateTime = 0;
    private SensorManager sensorManager;
    private boolean motionActive = false;
    private int stabilityCounter = 0;
    private static final float MOTION_THRESHOLD = 0.5f;
    
    public LunarDriftWallpaper(Context context, SurfaceHolder surfaceHolder) {
        this.context = context;
        this.surfaceHolder = surfaceHolder;
        this.sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        this.lastUpdateTime = System.currentTimeMillis();
    }
    
    public void startRendering() {
        if (isRendering) return;
        isRendering = true;
        
        if (sensorManager != null) {
            Sensor gyro = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
            if (gyro != null) {
                sensorManager.registerListener(this, gyro, SensorManager.SENSOR_DELAY_NORMAL);
            }
        }
        
        renderTimer = new Timer();
        renderTimer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                updateAndRender();
            }
        }, 0, 16); // ~60 FPS
    }
    
    public void stopRendering() {
        isRendering = false;
        if (renderTimer != null) {
            renderTimer.cancel();
        }
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
    }
    
    private void updateAndRender() {
        if (!isRendering || surfaceHolder == null) return;
        
        Canvas canvas = null;
        try {
            canvas = surfaceHolder.lockCanvas();
            if (canvas != null) {
                drawFrame(canvas);
            }
        } finally {
            if (canvas != null) {
                surfaceHolder.unlockCanvasAndPost(canvas);
            }
        }
    }
    
    private void drawFrame(Canvas canvas) {
        long currentTime = System.currentTimeMillis();
        float dt = (currentTime - lastUpdateTime) / 1000.0f;
        lastUpdateTime = currentTime;
        
        // Clear background
        canvas.drawColor(Color.rgb(13, 13, 38));
        
        // Update rotation
        rotation += 5 * dt;
        if (!motionActive) {
            rotation += 2 * dt;
        }
        
        // Update tilt based on gyroscope
        tilt = (float) (Math.sin(currentTime / 1000.0f * 0.5f) * 15);
        
        // Draw stars
        Paint starPaint = new Paint();
        starPaint.setColor(Color.rgb(255, 255, 255));
        starPaint.setStrokeWidth(2);
        starPaint.setAlpha(200);
        
        int width = canvas.getWidth();
        int height = canvas.getHeight();
        
        // Draw procedural stars
        java.util.Random random = new java.util.Random(42);
        for (int i = 0; i < 100; i++) {
            float x = width * (i % 10) / 10.0f + random.nextFloat() * width / 10;
            float y = height * (i / 10) / 10.0f + random.nextFloat() * height / 10;
            canvas.drawCircle(x, y, 2, starPaint);
        }
        
        // Draw moon
        float centerX = width / 2.0f;
        float centerY = height / 2.0f;
        float moonRadius = Math.min(width, height) / 4.0f * pulse;
        
        // Moon glow
        Paint glowPaint = new Paint();
        glowPaint.setColor(Color.rgb(204, 204, 255));
        glowPaint.setAlpha((int)(80 * 0.5f));
        canvas.drawCircle(centerX, centerY, moonRadius * 1.3f, glowPaint);
        
        // Moon body
        Paint moonPaint = new Paint();
        moonPaint.setColor(Color.rgb(230, 230, 242));
        canvas.drawCircle(centerX, centerY, moonRadius, moonPaint);
        
        // Moon surface detail
        Paint cratePaint = new Paint();
        cratePaint.setColor(Color.rgb(200, 200, 220));
        float craterRadius = moonRadius * 0.15f;
        
        // Draw craters
        float[] craterPositions = {
            centerX - moonRadius * 0.3f, centerY - moonRadius * 0.2f,
            centerX + moonRadius * 0.2f, centerY + moonRadius * 0.3f,
            centerX - moonRadius * 0.1f, centerY + moonRadius * 0.1f,
        };
        
        for (int i = 0; i < craterPositions.length; i += 2) {
            canvas.drawCircle(craterPositions[i], craterPositions[i + 1], craterRadius, cratePaint);
        }
    }
    
    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() == Sensor.TYPE_GYROSCOPE) {
            gyroX = event.values[0];
            gyroY = event.values[1];
            gyroZ = event.values[2];
            
            float motion = Math.abs(gyroX) + Math.abs(gyroY) + Math.abs(gyroZ);
            
            if (motion < MOTION_THRESHOLD) {
                stabilityCounter++;
                if (stabilityCounter >= 30) {
                    motionActive = false;
                }
            } else {
                stabilityCounter = 0;
                motionActive = true;
            }
        }
    }
    
    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // Not used
    }
}
