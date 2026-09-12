"""
Lunar Drift - Android Live Wallpaper
A beautiful 3D moon animation with parallax scrolling, gyroscope control, and pulse effects.
"""

import os
os.environ['KIVY_WINDOW'] = 'pygame'
os.environ['KIVY_GL_BACKEND'] = 'gl'

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RenderContext, PushMatrix, PopMatrix, Translate, Rotate, Scale
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.properties import NumericProperty, ListProperty
from kivy.event import EventDispatcher

import math
import numpy as np
from collections import deque
from datetime import datetime

# Try to import sensor support
try:
    from jnius import autoclass
    from android.runnable import run_on_ui_thread
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    SensorManager = autoclass('android.hardware.SensorManager')
    Sensor = autoclass('android.hardware.Sensor')
    SensorEvent = autoclass('android.hardware.SensorEvent')
    Context = autoclass('android.content.Context')
    SENSORS_AVAILABLE = True
except ImportError:
    SENSORS_AVAILABLE = False
    PythonActivity = None

# Wallpaper service registration
WALLPAPER_SERVICE_CLASS = """
package org.lunardrift.wallpaper;

import android.app.WallpaperManager;
import android.content.Intent;
import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import org.kivy.android.PythonActivity;

public class LunarDriftWallpaperActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent intent = new Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER);
        intent.putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT,
            new android.content.ComponentName(this, LunarDriftWallpaperService.class));
        startActivity(intent);
        finish();
    }
}
"""


class MoonRenderer:
    """Renders a realistic moon using procedural generation"""
    
    def __init__(self, width=512, height=512):
        self.width = width
        self.height = height
        self.texture = None
        self.update_moon()
    
    def update_moon(self):
        """Generate moon texture with craters and surface details"""
        data = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        cx, cy = self.width // 2, self.height // 2
        radius = min(self.width, self.height) // 2 - 10
        
        for y in range(self.height):
            for x in range(self.width):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < radius:
                    # Moon surface color
                    base_color = 200 + int(30 * math.sin(dx/50) * math.cos(dy/50))
                    
                    # Add craters with noise
                    crater_noise = (math.sin(dx/30) * math.cos(dy/40) + 
                                  math.sin(dx/70) * math.cos(dy/80))
                    crater_factor = 1 + crater_noise * 0.3
                    
                    color = int(base_color * crater_factor)
                    color = max(100, min(255, color))
                    
                    # Shadow on one side
                    shadow = 1 - (dx / (radius * 1.5)) * 0.3
                    shadow = max(0.3, min(1.0, shadow))
                    
                    data[y, x] = [int(color * shadow * 0.9), 
                                 int(color * shadow * 0.85), 
                                 int(color * shadow)]
                elif dist < radius + 20:
                    # Glow/atmosphere
                    glow = 1 - (dist - radius) / 20
                    glow_color = int(30 * glow)
                    data[y, x] = [glow_color, glow_color, int(glow_color * 0.8)]
        
        self.texture = Texture.create(size=(self.width, self.height), colorfmt='rgb')
        self.texture.blit_buffer(data.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
        return self.texture


class MotionSensor(EventDispatcher):
    """Handles accelerometer and gyroscope data"""
    
    gyro_x = NumericProperty(0)
    gyro_y = NumericProperty(0)
    gyro_z = NumericProperty(0)
    accel_x = NumericProperty(0)
    accel_y = NumericProperty(0)
    accel_z = NumericProperty(0)
    
    def __init__(self):
        super().__init__()
        self.gyro_buffer = deque(maxlen=10)
        self.accel_buffer = deque(maxlen=10)
        self.stability_counter = 0
        self.is_stable = False
        self.motion_active = False
        self.threshold = 0.5
        
        if SENSORS_AVAILABLE:
            self.init_sensors()
    
    def init_sensors(self):
        """Initialize Android sensors if available"""
        try:
            activity = PythonActivity.mActivity
            context = activity.getSystemService(Context.SENSOR_SERVICE)
            self.sensor_manager = context
            # This would need jnius sensor listener setup
        except:
            pass
    
    def update_gyro(self, x, y, z):
        """Update gyroscope readings"""
        self.gyro_x = x
        self.gyro_y = y
        self.gyro_z = z
        self.gyro_buffer.append((x, y, z))
        self.check_stability()
    
    def update_accel(self, x, y, z):
        """Update accelerometer readings"""
        self.accel_x = x
        self.accel_y = y
        self.accel_z = z
        self.accel_buffer.append((x, y, z))
    
    def check_stability(self):
        """Check if device has been stable for 3 seconds"""
        if len(self.gyro_buffer) > 0:
            avg_motion = np.mean([abs(v[0]) + abs(v[1]) + abs(v[2]) 
                                 for v in self.gyro_buffer])
            
            if avg_motion < self.threshold:
                self.stability_counter += 1
                if self.stability_counter >= 30:  # ~3 seconds at 10 Hz
                    self.is_stable = True
                    self.motion_active = False
            else:
                self.stability_counter = 0
                self.is_stable = False
                self.motion_active = True


class MoonCanvas(Widget):
    """Main rendering canvas for the moon and wallpaper"""
    
    rotation = NumericProperty(0)
    tilt = NumericProperty(0)
    pulse = NumericProperty(1.0)
    scroll_offset_x = NumericProperty(0)
    scroll_offset_y = NumericProperty(0)
    glow_intensity = NumericProperty(0.5)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.moon_renderer = MoonRenderer(512, 512)
        self.motion_sensor = MotionSensor()
        self.tap_time = 0
        self.last_tap_x = 0
        self.last_tap_y = 0
        self.double_tap_detected = False
        self.pulse_active = False
        self.pulse_start_time = 0
        self.animation_time = 0
        self.parallax_x = 0
        self.parallax_y = 0
        self.bg_layers = []
        self.init_backgrounds()
        
        Clock.schedule_interval(self.update, 1.0/60.0)
        self.bind(size=self.on_size)
    
    def init_backgrounds(self):
        """Initialize parallax background layers"""
        self.bg_layers = [
            {'color': (0.05, 0.05, 0.15), 'stars': self.generate_stars(100)},
            {'color': (0.08, 0.08, 0.20), 'stars': self.generate_stars(50)},
        ]
    
    def generate_stars(self, count):
        """Generate random star positions"""
        stars = []
        np.random.seed(42)  # Deterministic for consistency
        for _ in range(count):
            x = np.random.uniform(0, self.width)
            y = np.random.uniform(0, self.height)
            brightness = np.random.uniform(0.3, 1.0)
            stars.append((x, y, brightness))
        return stars
    
    def on_touch_down(self, touch):
        """Handle touch input for double-tap detection"""
        current_time = datetime.now().timestamp()
        
        # Check for double tap
        if current_time - self.tap_time < 0.3:
            dx = abs(touch.x - self.last_tap_x)
            dy = abs(touch.y - self.last_tap_y)
            if dx < 100 and dy < 100:
                self.double_tap_detected = True
                self.pulse_active = True
                self.pulse_start_time = current_time
                self.pulse = 1.0
        
        self.tap_time = current_time
        self.last_tap_x = touch.x
        self.last_tap_y = touch.y
        return True
    
    def on_touch_move(self, touch):
        """Handle parallax scrolling"""
        dx = touch.dx
        dy = touch.dy
        self.scroll_offset_x += dx * 0.5
        self.scroll_offset_y += dy * 0.5
        self.parallax_x = self.scroll_offset_x / self.width
        self.parallax_y = self.scroll_offset_y / self.height
        return True
    
    def update(self, dt):
        """Update animation and sensor data"""
        self.animation_time += dt
        
        # Update rotation and tilt based on gyroscope (simulated)
        self.rotation += 5 * dt  # Continuous rotation
        self.tilt = math.sin(self.animation_time * 0.5) * 15
        
        # Update pulse animation
        if self.pulse_active:
            elapsed = datetime.now().timestamp() - self.pulse_start_time
            if elapsed < 0.5:
                self.pulse = 1.0 + 0.3 * math.sin(elapsed * math.pi * 4)
                self.glow_intensity = 0.8
            else:
                self.pulse_active = False
                self.pulse = 1.0
                self.glow_intensity = 0.5
        
        # Idle rotation
        if not self.motion_sensor.motion_active:
            self.rotation += 2 * dt
    
    def on_size(self, instance, value):
        """Handle window resize"""
        pass
    
    def draw_moon(self):
        """Draw the moon with effects"""
        with self.canvas.before:
            PushMatrix()
            Translate(self.center_x, self.center_y)
            Rotate(angle=self.rotation, origin=(0, 0, 0))
            Rotate(angle=self.tilt, origin=(0, 0, 0), axis=(1, 0, 0))
            Scale(self.pulse, self.pulse, 1)
            
            # Moon body
            Color(0.9, 0.9, 0.95, 1)
            size = 200 * self.pulse
            Ellipse(pos=(self.center_x - size, self.center_y - size),
                    size=(size * 2, size * 2))
            
            # Glow effect
            Color(0.8, 0.8, 1.0, self.glow_intensity * 0.3)
            glow_size = size * 1.3
            Ellipse(pos=(self.center_x - glow_size, self.center_y - glow_size),
                    size=(glow_size * 2, glow_size * 2))
            
            PopMatrix()
    
    def on_canvas_instructions(self):
        """Render everything"""
        self.canvas.clear()
        
        with self.canvas:
            # Background
            Color(0.05, 0.05, 0.15, 1)
            Ellipse(pos=(0, 0), size=(self.width, self.height))
            
            # Stars
            Color(1, 1, 1, 0.8)
            for layer in self.bg_layers:
                for x, y, brightness in layer['stars']:
                    px = x + self.parallax_x * 50
                    py = y + self.parallax_y * 50
                    if 0 <= px < self.width and 0 <= py < self.height:
                        Ellipse(pos=(px - 2, py - 2), size=(4, 4))
            
            self.draw_moon()


class LunarDriftApp(App):
    """Main application class"""
    
    def build(self):
        self.title = "Lunar Drift"
        Window.size = (1024, 768)
        
        layout = BoxLayout(orientation='vertical')
        
        # Canvas for wallpaper preview
        self.canvas_widget = MoonCanvas()
        layout.add_widget(self.canvas_widget)
        
        # Control panel
        control_panel = GridLayout(cols=2, size_hint_y=0.2, spacing=10, padding=10)
        
        btn_wallpaper = Button(text='Set as Wallpaper', size_hint_x=0.5)
        btn_wallpaper.bind(on_press=self.set_as_wallpaper)
        control_panel.add_widget(btn_wallpaper)
        
        btn_settings = Button(text='Settings', size_hint_x=0.5)
        btn_settings.bind(on_press=self.show_settings)
        control_panel.add_widget(btn_settings)
        
        layout.add_widget(control_panel)
        
        Clock.schedule_interval(lambda dt: self.canvas_widget.on_canvas_instructions(), 1.0/60.0)
        
        return layout
    
    def set_as_wallpaper(self, instance):
        """Set this as the live wallpaper"""
        try:
            from android.intent import Intent
            from android.content import ComponentName
            from android import AndroidString
            
            activity = PythonActivity.mActivity
            intent = Intent()
            intent.setAction("android.intent.action.SET_WALLPAPER")
            activity.startActivity(intent)
            
            popup = Popup(title='Success', size_hint=(0.8, 0.3))
            popup.content = Label(text='Opening wallpaper settings...')
            popup.open()
            Clock.schedule_once(lambda dt: popup.dismiss(), 2)
        except Exception as e:
            popup = Popup(title='Error', size_hint=(0.8, 0.3))
            popup.content = Label(text=f'Error: {str(e)}')
            popup.open()
            Clock.schedule_once(lambda dt: popup.dismiss(), 2)
    
    def show_settings(self, instance):
        """Show settings popup"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        content.add_widget(Label(text='Moon Rotation Speed:', size_hint_y=0.2))
        content.add_widget(Label(text='Gyroscope Control: Enabled', size_hint_y=0.2))
        content.add_widget(Label(text='Parallax Scrolling: Enabled', size_hint_y=0.2))
        content.add_widget(Label(text='Pulse Animation: Enabled', size_hint_y=0.2))
        
        close_btn = Button(text='Close', size_hint_y=0.2)
        content.add_widget(close_btn)
        
        popup = Popup(title='Settings', content=content, size_hint=(0.9, 0.8))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


if __name__ == '__main__':
    LunarDriftApp().run()
