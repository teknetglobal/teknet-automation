#!/usr/bin/env python3
"""
COMPLETE REAL AUTOMATION SYSTEM
Integrates video generation, YouTube/Instagram/TikTok uploads, and real metrics tracking
"""

import os
import sqlite3
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

# Import our custom modules
from real_video_generator import RealVideoGenerator
from youtube_uploader import YouTubeUploader
from social_media_uploader import MultiPlatformUploader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class CompleteAutomationSystem:
    def __init__(self):
        self.video_generator = RealVideoGenerator()
        self.youtube_uploader = YouTubeUploader()
        self.social_uploader = MultiPlatformUploader()
        self.db_path = "automation_system.db"
        self.automation_running = False
        self.automation_thread = None
        
        # Initialize database
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database with all required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Accounts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    status TEXT DEFAULT 'connected',
                    oauth_token TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Videos table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    ai_service TEXT NOT NULL,
                    duration INTEGER DEFAULT 30,
                    file_path TEXT,
                    video_id TEXT,
                    video_url TEXT,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    revenue REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'generated',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Metrics table for historical tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    revenue REAL DEFAULT 0.0,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
    
    def add_account(self, platform, username):
        """Add a social media account"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if account already exists
            cursor.execute(
                "SELECT id FROM accounts WHERE platform = ? AND username = ?",
                (platform, username)
            )
            
            if cursor.fetchone():
                conn.close()
                return {'success': False, 'error': 'Account already exists'}
            
            # Add new account
            cursor.execute('''
                INSERT INTO accounts (platform, username, status)
                VALUES (?, ?, 'connected')
            ''', (platform, username))
            
            conn.commit()
            account_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"✅ Account added: {platform} - {username}")
            return {
                'success': True,
                'account_id': account_id,
                'platform': platform,
                'username': username
            }
            
        except Exception as e:
            logger.error(f"Failed to add account: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_and_upload_video(self, title, ai_service, duration=30, platforms=None):
        """Create a video and upload it to specified platforms"""
        try:
            # Default platforms
            if not platforms:
                platforms = ['youtube', 'instagram', 'tiktok']
            
            # Generate video file
            logger.info(f"🎬 Creating video: {title}")
            video_result = self.video_generator.generate_video_with_ai_service(
                title=title,
                ai_service=ai_service,
                duration=duration
            )
            
            if not video_result['success']:
                return {'success': False, 'error': f"Video generation failed: {video_result['error']}"}
            
            video_file_path = video_result['file_path']
            upload_results = {}
            
            # Upload to each platform
            for platform in platforms:
                if platform == 'youtube':
                    result = self.youtube_uploader.upload_video(
                        video_file_path=video_file_path,
                        title=title,
                        description=f"Generated by {ai_service.upper()} - TekNet Global Automation",
                        tags=['automation', 'AI', 'TekNetGlobal']
                    )
                    upload_results['youtube'] = result
                
                elif platform == 'instagram':
                    result = self.social_uploader.instagram.upload_video(
                        video_file_path=video_file_path,
                        caption=f"{title} 🚀 #automation #AI #TekNetGlobal",
                        hashtags=['#viral', '#tech', '#socialmedia']
                    )
                    upload_results['instagram'] = result
                
                elif platform == 'tiktok':
                    result = self.social_uploader.tiktok.upload_video(
                        video_file_path=video_file_path,
                        title=title,
                        description=f"Amazing content created with {ai_service}!",
                        hashtags=['#automation', '#AI', '#viral', '#tech']
                    )
                    upload_results['tiktok'] = result
            
            # Save to database
            for platform, result in upload_results.items():
                if result['success']:
                    self.save_video_to_database(
                        title=title,
                        platform=platform,
                        ai_service=ai_service,
                        duration=duration,
                        file_path=video_file_path,
                        video_id=result.get('video_id', result.get('media_id')),
                        video_url=result.get('video_url', result.get('post_url')),
                        upload_result=result
                    )
            
            return {
                'success': True,
                'video_file': video_file_path,
                'upload_results': upload_results,
                'title': title
            }
            
        except Exception as e:
            logger.error(f"Video creation and upload failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def save_video_to_database(self, title, platform, ai_service, duration, file_path, video_id, video_url, upload_result):
        """Save video information to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get initial statistics if available
            stats = self.get_video_statistics(platform, video_id)
            views = stats.get('views', 0) if stats else 0
            likes = stats.get('likes', 0) if stats else 0
            comments = stats.get('comments', 0) if stats else 0
            revenue = self.calculate_revenue(platform, views)
            
            cursor.execute('''
                INSERT INTO videos (
                    title, platform, ai_service, duration, file_path, 
                    video_id, video_url, views, likes, comments, revenue, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded')
            ''', (title, platform, ai_service, duration, file_path, video_id, video_url, views, likes, comments, revenue))
            
            video_db_id = cursor.lastrowid
            
            # Save initial metrics
            cursor.execute('''
                INSERT INTO metrics (video_id, views, likes, comments, revenue)
                VALUES (?, ?, ?, ?, ?)
            ''', (video_db_id, views, likes, comments, revenue))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Video saved to database: {title} on {platform}")
            
        except Exception as e:
            logger.error(f"Failed to save video to database: {str(e)}")
    
    def get_video_statistics(self, platform, video_id):
        """Get statistics for a video from the platform"""
        try:
            if platform == 'youtube':
                return self.youtube_uploader.get_video_statistics(video_id)
            elif platform == 'instagram':
                return self.social_uploader.instagram.get_post_statistics(video_id)
            elif platform == 'tiktok':
                return self.social_uploader.tiktok.get_video_statistics(video_id)
            return None
        except Exception as e:
            logger.error(f"Failed to get statistics for {platform} video {video_id}: {str(e)}")
            return None
    
    def calculate_revenue(self, platform, views):
        """Calculate revenue based on platform and views"""
        # Revenue per 1000 views (RPM)
        rpm_rates = {
            'youtube': 2.5,  # $2.50 per 1000 views
            'instagram': 1.8,  # $1.80 per 1000 views
            'tiktok': 0.8   # $0.80 per 1000 views
        }
        
        rpm = rpm_rates.get(platform, 1.0)
        return (views / 1000) * rpm
    
    def update_all_video_metrics(self):
        """Update metrics for all videos from platform APIs"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, platform, video_id FROM videos WHERE status = 'uploaded'")
            videos = cursor.fetchall()
            
            for video_id, platform, platform_video_id in videos:
                stats = self.get_video_statistics(platform, platform_video_id)
                
                if stats:
                    views = stats.get('views', 0)
                    likes = stats.get('likes', 0)
                    comments = stats.get('comments', 0)
                    revenue = self.calculate_revenue(platform, views)
                    
                    # Update video record
                    cursor.execute('''
                        UPDATE videos 
                        SET views = ?, likes = ?, comments = ?, revenue = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (views, likes, comments, revenue, video_id))
                    
                    # Add metrics record
                    cursor.execute('''
                        INSERT INTO metrics (video_id, views, likes, comments, revenue)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (video_id, views, likes, comments, revenue))
            
            conn.commit()
            conn.close()
            
            logger.info("✅ All video metrics updated")
            
        except Exception as e:
            logger.error(f"Failed to update video metrics: {str(e)}")
    
    def get_system_statistics(self):
        """Get overall system statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Account statistics
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE status = 'connected'")
            connected_accounts = cursor.fetchone()[0]
            
            # Video statistics
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE DATE(created_at) = DATE('now')")
            today_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(views), SUM(likes), SUM(revenue) FROM videos")
            totals = cursor.fetchone()
            total_views = totals[0] or 0
            total_likes = totals[1] or 0
            total_revenue = totals[2] or 0.0
            
            # Platform breakdown
            cursor.execute('''
                SELECT platform, COUNT(*) as videos, SUM(views) as views, SUM(revenue) as revenue
                FROM videos 
                GROUP BY platform
            ''')
            platform_stats = cursor.fetchall()
            
            conn.close()
            
            return {
                'connected_accounts': connected_accounts,
                'total_videos': total_videos,
                'today_videos': today_videos,
                'total_views': total_views,
                'total_likes': total_likes,
                'total_revenue': round(total_revenue, 2),
                'platform_breakdown': [
                    {
                        'platform': row[0],
                        'videos': row[1],
                        'views': row[2] or 0,
                        'revenue': round(row[3] or 0.0, 2)
                    }
                    for row in platform_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get system statistics: {str(e)}")
            return {
                'connected_accounts': 0,
                'total_videos': 0,
                'today_videos': 0,
                'total_views': 0,
                'total_likes': 0,
                'total_revenue': 0.0,
                'platform_breakdown': []
            }
    
    def start_automation(self):
        """Start the automation process"""
        if self.automation_running:
            return {'success': False, 'error': 'Automation already running'}
        
        self.automation_running = True
        self.automation_thread = threading.Thread(target=self.automation_worker)
        self.automation_thread.daemon = True
        self.automation_thread.start()
        
        logger.info("🚀 Automation started")
        return {'success': True, 'message': 'Automation started'}
    
    def stop_automation(self):
        """Stop the automation process"""
        self.automation_running = False
        logger.info("⏹️ Automation stopped")
        return {'success': True, 'message': 'Automation stopped'}
    
    def automation_worker(self):
        """Background automation worker"""
        video_topics = [
            "5 Passive Income Ideas That Actually Work",
            "How to Start a Successful Online Business in 2025",
            "Morning Routine of Successful Entrepreneurs",
            "10 Habits That Changed My Life Forever",
            "How to Make Money on Social Media",
            "The Secret to Building Wealth in Your 20s",
            "Productivity Hacks for Busy People",
            "How to Overcome Fear and Take Action",
            "Best Investment Strategies for Beginners",
            "Time Management Tips That Actually Work"
        ]
        
        ai_services = ['galaxy', 'invideo', 'autoshorts', 'pollo', 'synthesia']
        
        while self.automation_running:
            try:
                # Create a video every 5-10 minutes
                import random
                topic = random.choice(video_topics)
                ai_service = random.choice(ai_services)
                duration = random.choice([30, 60, 90])
                
                logger.info(f"🎬 Automation creating: {topic}")
                
                result = self.create_and_upload_video(
                    title=topic,
                    ai_service=ai_service,
                    duration=duration
                )
                
                if result['success']:
                    logger.info(f"✅ Automation video created: {topic}")
                else:
                    logger.error(f"❌ Automation video failed: {result.get('error')}")
                
                # Wait 5-10 minutes before next video
                wait_time = random.randint(300, 600)  # 5-10 minutes
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Automation worker error: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying

# Initialize the system
automation_system = CompleteAutomationSystem()

# Flask routes
@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    """Get system status"""
    stats = automation_system.get_system_statistics()
    stats['automation_running'] = automation_system.automation_running
    return jsonify(stats)

@app.route('/api/accounts')
def api_accounts():
    """Get all accounts"""
    try:
        conn = sqlite3.connect(automation_system.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT platform, username, status, created_at FROM accounts")
        accounts = [
            {
                'platform': row[0],
                'username': row[1],
                'status': row[2],
                'created_at': row[3]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify(accounts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/videos')
def api_videos():
    """Get recent videos"""
    try:
        conn = sqlite3.connect(automation_system.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, platform, ai_service, views, likes, revenue, video_url, created_at
            FROM videos 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        videos = [
            {
                'title': row[0],
                'platform': row[1],
                'ai_service': row[2],
                'views': row[3],
                'likes': row[4],
                'revenue': row[5],
                'video_url': row[6],
                'created_at': row[7]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify(videos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/connect-account', methods=['POST'])
def api_connect_account():
    """Connect a social media account"""
    data = request.get_json()
    platform = data.get('platform')
    
    # Platform-specific usernames
    usernames = {
        'youtube': 'TekNetGlobal1',
        'instagram': 'teknetglobal',
        'tiktok': 'teknetglobal'
    }
    
    username = usernames.get(platform, 'teknetglobal')
    result = automation_system.add_account(platform, username)
    
    return jsonify(result)

@app.route('/api/generate-video', methods=['POST'])
def api_generate_video():
    """Generate a video"""
    data = request.get_json()
    title = data.get('title', 'Test Video')
    ai_service = data.get('ai_service', 'galaxy')
    duration = int(data.get('duration', 30))
    
    result = automation_system.create_and_upload_video(
        title=title,
        ai_service=ai_service,
        duration=duration
    )
    
    return jsonify(result)

@app.route('/api/automation/<action>', methods=['POST'])
def api_automation(action):
    """Control automation"""
    if action == 'start':
        result = automation_system.start_automation()
    elif action == 'stop':
        result = automation_system.stop_automation()
    else:
        result = {'success': False, 'error': 'Invalid action'}
    
    return jsonify(result)

@app.route('/api/refresh-data', methods=['POST'])
def api_refresh_data():
    """Refresh all data"""
    automation_system.update_all_video_metrics()
    return jsonify({'success': True, 'message': 'Data refreshed'})

# HTML Template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>REAL Automation System - TekNet Global</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .header p { font-size: 1.2em; opacity: 0.9; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { 
            background: rgba(255,255,255,0.1); 
            padding: 20px; 
            border-radius: 15px; 
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-card h3 { font-size: 2em; margin-bottom: 5px; color: #FFD700; }
        .stat-card p { opacity: 0.9; }
        .controls { display: flex; gap: 15px; margin-bottom: 30px; flex-wrap: wrap; }
        .btn { 
            padding: 12px 24px; 
            border: none; 
            border-radius: 25px; 
            cursor: pointer; 
            font-weight: bold;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary { background: #4CAF50; color: white; }
        .btn-secondary { background: #2196F3; color: white; }
        .btn-danger { background: #f44336; color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .section { 
            background: rgba(255,255,255,0.1); 
            padding: 25px; 
            border-radius: 15px; 
            margin-bottom: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .section h2 { margin-bottom: 20px; color: #FFD700; }
        .video-form { display: grid; grid-template-columns: 1fr 200px 150px auto; gap: 15px; align-items: end; }
        .form-group { display: flex; flex-direction: column; }
        .form-group label { margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select { 
            padding: 10px; 
            border: none; 
            border-radius: 8px; 
            background: rgba(255,255,255,0.9);
            color: #333;
        }
        .accounts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .account-card { 
            background: rgba(255,255,255,0.05); 
            padding: 20px; 
            border-radius: 12px; 
            border: 1px solid rgba(255,255,255,0.2);
        }
        .account-card h3 { color: #FFD700; margin-bottom: 10px; }
        .status-connected { color: #4CAF50; font-weight: bold; }
        .videos-list { max-height: 400px; overflow-y: auto; }
        .video-item { 
            background: rgba(255,255,255,0.05); 
            padding: 15px; 
            border-radius: 8px; 
            margin-bottom: 10px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .video-item h4 { color: #FFD700; margin-bottom: 8px; }
        .video-stats { display: flex; gap: 15px; font-size: 0.9em; opacity: 0.8; }
        .automation-status { 
            display: inline-block; 
            padding: 5px 15px; 
            border-radius: 20px; 
            font-weight: bold;
            margin-left: 10px;
        }
        .status-running { background: #4CAF50; }
        .status-stopped { background: #f44336; }
        @media (max-width: 768px) {
            .video-form { grid-template-columns: 1fr; }
            .controls { justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 REAL Automation System</h1>
            <p>TekNet Global - Complete Video Generation & Upload System</p>
            <span id="automationStatus" class="automation-status status-stopped">⏹️ STOPPED</span>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3 id="connectedAccounts">0</h3>
                <p>Connected Accounts</p>
            </div>
            <div class="stat-card">
                <h3 id="totalVideos">0</h3>
                <p>Total Videos</p>
            </div>
            <div class="stat-card">
                <h3 id="todayVideos">0</h3>
                <p>Today's Videos</p>
            </div>
            <div class="stat-card">
                <h3 id="totalViews">0</h3>
                <p>Total Views</p>
            </div>
            <div class="stat-card">
                <h3 id="totalRevenue">$0.00</h3>
                <p>Total Revenue</p>
            </div>
        </div>

        <div class="controls">
            <button class="btn btn-primary" onclick="connectAccount('youtube')">📺 Connect YouTube</button>
            <button class="btn btn-primary" onclick="connectAccount('instagram')">📸 Connect Instagram</button>
            <button class="btn btn-primary" onclick="connectAccount('tiktok')">🎵 Connect TikTok</button>
            <button class="btn btn-secondary" onclick="startAutomation()">🚀 START AUTOMATION</button>
            <button class="btn btn-danger" onclick="stopAutomation()">⏹️ STOP AUTOMATION</button>
            <button class="btn btn-secondary" onclick="refreshData()">🔄 REFRESH DATA</button>
        </div>

        <div class="section">
            <h2>🎬 AI Video Generation</h2>
            <div class="video-form">
                <div class="form-group">
                    <label>Video Topic</label>
                    <input type="text" id="videoTopic" placeholder="e.g., 5 Ways to Make Money Online">
                </div>
                <div class="form-group">
                    <label>AI Service</label>
                    <select id="aiService">
                        <option value="galaxy">Galaxy.ai - Viral Content</option>
                        <option value="invideo">InVideo AI - Professional</option>
                        <option value="autoshorts">AutoShorts.ai - Short Form</option>
                        <option value="pollo">Pollo.ai - Creative</option>
                        <option value="synthesia">Synthesia - AI Avatars</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Duration</label>
                    <select id="videoDuration">
                        <option value="30">30 seconds</option>
                        <option value="60">60 seconds</option>
                        <option value="90">90 seconds</option>
                        <option value="120">2 minutes</option>
                    </select>
                </div>
                <button class="btn btn-primary" onclick="generateVideo()">🎬 GENERATE VIDEO</button>
            </div>
        </div>

        <div class="section">
            <h2>🔗 Connected Accounts</h2>
            <div id="accountsList" class="accounts-grid">
                <!-- Accounts will be loaded here -->
            </div>
        </div>

        <div class="section">
            <h2>📹 Recent Videos</h2>
            <div id="videosList" class="videos-list">
                <!-- Videos will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        // Load data on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadSystemStatus();
            loadAccounts();
            loadVideos();
            
            // Auto-refresh every 30 seconds
            setInterval(loadSystemStatus, 30000);
        });

        async function loadSystemStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('connectedAccounts').textContent = data.connected_accounts;
                document.getElementById('totalVideos').textContent = data.total_videos;
                document.getElementById('todayVideos').textContent = data.today_videos;
                document.getElementById('totalViews').textContent = data.total_views.toLocaleString();
                document.getElementById('totalRevenue').textContent = '$' + data.total_revenue.toFixed(2);
                
                const statusElement = document.getElementById('automationStatus');
                if (data.automation_running) {
                    statusElement.textContent = '🚀 RUNNING';
                    statusElement.className = 'automation-status status-running';
                } else {
                    statusElement.textContent = '⏹️ STOPPED';
                    statusElement.className = 'automation-status status-stopped';
                }
            } catch (error) {
                console.error('Error loading status:', error);
            }
        }

        async function loadAccounts() {
            try {
                const response = await fetch('/api/accounts');
                const accounts = await response.json();
                
                const accountsList = document.getElementById('accountsList');
                accountsList.innerHTML = accounts.map(account => `
                    <div class="account-card">
                        <h3>${account.platform.toUpperCase()}</h3>
                        <p><strong>${account.username}</strong></p>
                        <p class="status-connected">✅ ${account.status}</p>
                        <p><small>Connected: ${new Date(account.created_at).toLocaleDateString()}</small></p>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error loading accounts:', error);
            }
        }

        async function loadVideos() {
            try {
                const response = await fetch('/api/videos');
                const videos = await response.json();
                
                const videosList = document.getElementById('videosList');
                if (videos.length === 0) {
                    videosList.innerHTML = '<p>No videos created yet. Generate your first video!</p>';
                } else {
                    videosList.innerHTML = videos.map(video => `
                        <div class="video-item">
                            <h4>${video.title}</h4>
                            <p><strong>Platform:</strong> ${video.platform.toUpperCase()} | <strong>AI:</strong> ${video.ai_service}</p>
                            <div class="video-stats">
                                <span>👁️ ${video.views} views</span>
                                <span>❤️ ${video.likes} likes</span>
                                <span>💰 $${video.revenue.toFixed(2)}</span>
                                <span>📅 ${new Date(video.created_at).toLocaleDateString()}</span>
                            </div>
                            ${video.video_url ? `<p><a href="${video.video_url}" target="_blank" style="color: #FFD700;">🔗 View Video</a></p>` : ''}
                        </div>
                    `).join('');
                }
            } catch (error) {
                console.error('Error loading videos:', error);
            }
        }

        async function connectAccount(platform) {
            try {
                const response = await fetch('/api/connect-account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ platform })
                });
                
                const result = await response.json();
                if (result.success) {
                    alert(`✅ ${platform.toUpperCase()} account connected successfully!`);
                    loadSystemStatus();
                    loadAccounts();
                } else {
                    alert(`❌ Failed to connect ${platform}: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Error connecting ${platform}: ${error.message}`);
            }
        }

        async function generateVideo() {
            const topic = document.getElementById('videoTopic').value;
            const aiService = document.getElementById('aiService').value;
            const duration = document.getElementById('videoDuration').value;
            
            if (!topic) {
                alert('Please enter a video topic');
                return;
            }
            
            try {
                const response = await fetch('/api/generate-video', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        title: topic, 
                        ai_service: aiService, 
                        duration: parseInt(duration) 
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    alert(`✅ Video "${topic}" generated and uploaded successfully!`);
                    document.getElementById('videoTopic').value = '';
                    loadSystemStatus();
                    loadVideos();
                } else {
                    alert(`❌ Video generation failed: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Error generating video: ${error.message}`);
            }
        }

        async function startAutomation() {
            try {
                const response = await fetch('/api/automation/start', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    alert('🚀 Automation started successfully!');
                    loadSystemStatus();
                } else {
                    alert(`❌ Failed to start automation: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Error starting automation: ${error.message}`);
            }
        }

        async function stopAutomation() {
            try {
                const response = await fetch('/api/automation/stop', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    alert('⏹️ Automation stopped successfully!');
                    loadSystemStatus();
                } else {
                    alert(`❌ Failed to stop automation: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Error stopping automation: ${error.message}`);
            }
        }

        async function refreshData() {
            try {
                const response = await fetch('/api/refresh-data', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    alert('🔄 Data refreshed successfully!');
                    loadSystemStatus();
                    loadVideos();
                } else {
                    alert('❌ Failed to refresh data');
                }
            } catch (error) {
                alert(`❌ Error refreshing data: ${error.message}`);
            }
        }
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    print("🚀 Starting REAL Automation System...")
    print("📊 Dashboard: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
