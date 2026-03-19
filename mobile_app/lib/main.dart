import 'dart:async';
import 'dart:convert';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui'; // For ImageFilter

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_tts/flutter_tts.dart';
import 'package:url_launcher/url_launcher.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cameras = await availableCameras();
  final firstCamera = cameras.firstWhere(
    (camera) => camera.lensDirection == CameraLensDirection.front,
    orElse: () => cameras.first,
  );

  runApp(MyApp(camera: firstCamera));
}

class MyApp extends StatelessWidget {
  final CameraDescription camera;

  const MyApp({super.key, required this.camera});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Face Security Dashboard',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0F172A), // --bg-color
        primaryColor: const Color(0xFF3B82F6), // --accent-blue
        cardColor: const Color(0xFF1E293B), // --card-bg
        colorScheme: const ColorScheme.dark(
            primary: Color(0xFF3B82F6),
            secondary: Color(0xFF22C55E), // --accent-green
            error: Color(0xFFEF4444), // --accent-red
            surface: Color(0xFF1E293B),
            background: Color(0xFF0F172A),
        ),
        fontFamily: 'Roboto', // Default, but use Inter if available
        useMaterial3: true,
      ),
      home: DashboardScreen(camera: camera),
    );
  }
}

class DashboardScreen extends StatefulWidget {
  final CameraDescription camera;

  const DashboardScreen({super.key, required this.camera});

  @override
  DashboardScreenState createState() => DashboardScreenState();
}

class DashboardScreenState extends State<DashboardScreen> {
  late CameraController _controller;
  late Future<void> _initializeControllerFuture;
  late FlutterTts _flutterTts;
  Timer? _scanTimer;
  bool _isScanning = false;
  String _statusMessage = "System Ready";
  Color _statusColor = const Color(0xFF3B82F6); // Blue
  String? _detectedName;
  List<Map<String, dynamic>> _detectedFaces = [];
  List<Map<String, dynamic>> _detectedObjects = [];
  DateTime? _lastSpeakTime;
  String? _lastSpokenName;
  int _speakCount = 0;
  int _intruderCount = 0;
  Timer? _historyTimer;
  
  String serverUrl = "http://127.0.0.1:5000"; // Default fallback
  
  Future<void> _discoverServer() async {
    if (kIsWeb) {
      print("UDP discovery is not supported on the web.");
      if (mounted) {
        setState(() {
          _statusMessage = "Web Mode: UDP features disabled";
        });
      }
      return;
    }

    try {
      final socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;
      final completer = Completer<String?>();
      
      socket.listen((RawSocketEvent event) {
        if (event == RawSocketEvent.read) {
          final datagram = socket.receive();
          if (datagram != null) {
            final message = utf8.decode(datagram.data);
            if (message.startsWith('FACE_SERVER_ACK')) {
              final port = message.split(':')[1];
              completer.complete("http://${datagram.address.address}:$port");
            }
          }
        }
      });
      
      try {
        socket.send(utf8.encode('DISCOVER_FACE_SERVER'), InternetAddress("255.255.255.255"), 5555);
      } catch (e) {
        print("Broadcast 255.255.255.255 failed: $e");
      }
      
      try {
        final interfaces = await NetworkInterface.list();
        for (var interface in interfaces) {
          for (var addr in interface.addresses) {
            final ipParts = addr.address.split('.');
            if (ipParts.length == 4) {
              ipParts[3] = '255';
              final broadcastIp = ipParts.join('.');
              try {
                socket.send(utf8.encode('DISCOVER_FACE_SERVER'), InternetAddress(broadcastIp), 5555);
              } catch (_) {}
            }
          }
        }
      } catch (e) {
        print("Interface broadcast failed: $e");
      }
      
      final result = await completer.future.timeout(
        const Duration(seconds: 3), 
        onTimeout: () {
          if (!completer.isCompleted) completer.complete(null);
          return null;
        }
      );
      socket.close();
      
      if (result != null && mounted) {
        setState(() {
          serverUrl = result;
          _statusMessage = "System Ready";
        });
      } else if (mounted) {
        setState(() {
          _statusMessage = "Server not found";
        });
        _promptForServerUrl();
      }
    } catch (e) {
      print("Discovery error: $e");
      if (mounted) _promptForServerUrl();
    }
  }

  Future<void> _promptForServerUrl() async {
    final TextEditingController ipController = TextEditingController();
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          title: const Text("Server Not Found"),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text("Automatic UDP discovery failed.\nPlease enter the Python server IP address manually (e.g., 192.168.1.100)."),
              const SizedBox(height: 16),
              TextField(
                controller: ipController,
                decoration: const InputDecoration(
                  labelText: "IP Address",
                  hintText: "192.168.1.100",
                  border: OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                final ip = ipController.text.trim();
                if (ip.isNotEmpty) {
                  setState(() {
                    serverUrl = "http://$ip:5000";
                    _statusMessage = "System Ready";
                  });
                  Navigator.of(context).pop();
                }
              },
              child: const Text("Save & Connect"),
            ),
          ],
        );
      },
    );
  }

  @override
  void initState() {
    super.initState();
    _statusMessage = "Searching for server...";
    
    _controller = CameraController(
      widget.camera,
      ResolutionPreset.medium, // Increase slightly for better detection?
      enableAudio: false,
    );
    _initializeControllerFuture = _controller.initialize();
    _initTts();
    
    _discoverServer().then((_) {
      _updateHistoryCount(); // Initial fetch
      _historyTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
          _updateHistoryCount();
      });
    });
  }
  
  bool _isFetchingHistory = false;

  Future<void> _updateHistoryCount() async {
      if (_isFetchingHistory) return;
      _isFetchingHistory = true;
      try {
          final history = await _fetchHistory();
          if (mounted) {
              setState(() {
                  _intruderCount = history.length;
              });
          }
      } catch (e) {
          print("History fetch error: $e");
      } finally {
          _isFetchingHistory = false;
      }
  }
  
  Future<void> _initTts() async {
    _flutterTts = FlutterTts();
    await _flutterTts.setLanguage("en-US");
    await _flutterTts.setSpeechRate(0.5);
    await _flutterTts.setVolume(1.0);
    await _flutterTts.setPitch(1.0);
  }
  
  Future<void> _speak(String text) async {
     await _flutterTts.speak(text);
  }

  @override
  void dispose() {
    _controller.dispose();
    _scanTimer?.cancel();
    _historyTimer?.cancel();
    _flutterTts.stop();
    super.dispose();
  }

  Future<String?> _captureAndEncode() async {
    try {
      if (!_controller.value.isInitialized || _controller.value.isTakingPicture) {
          return null;
      }
      final image = await _controller.takePicture();
      final bytes = await File(image.path).readAsBytes();
      return base64Encode(bytes);
    } catch (e) {
      print("Error capturing image: $e");
      return null;
    }
  }

  Future<void> _registerUser() async {
    TextEditingController nameController = TextEditingController();
    
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.9,
          minChildSize: 0.8,
          maxChildSize: 0.95,
          builder: (_, controller) {
            return ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B).withOpacity(0.95),
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                    border: Border(top: BorderSide(color: Colors.white.withOpacity(0.1)))
                  ),
                  padding: EdgeInsets.only(
                    bottom: MediaQuery.of(context).viewInsets.bottom,
                    left: 24, right: 24, top: 24
                  ),
                  child: ListView(
                    controller: controller, // Important for DraggableScrollableSheet
                    padding: EdgeInsets.only(
                      bottom: MediaQuery.of(context).viewInsets.bottom + 24, // Add keyboard padding + extra
                      left: 24, right: 24, top: 24
                    ),
                    children: [
                       Center(
                         child: Container(
                           width: 40, height: 4, 
                           margin: const EdgeInsets.only(bottom: 24),
                           decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(2))
                         ),
                       ),
                       const Text("Register New Face", style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                       const SizedBox(height: 8),
                       Text("Follow these steps to ensure accurate recognition.", style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14)),
                       const SizedBox(height: 32),
                       
                       // Step 1: Safety Instructions
                       _buildInstructionItem(Icons.light_mode, "Ensure good lighting on your face."),
                       _buildInstructionItem(Icons.remove_red_eye, "Look directly at the camera at eye level."),
                       _buildInstructionItem(Icons.face, "Keep a neutral expression."),
                       _buildInstructionItem(Icons.person_off, "Make sure no one else is in the frame."),
                       
                       const SizedBox(height: 32),
                       
                       // Step 2: Input & Action
                       TextField(
                          controller: nameController,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                              labelText: "Person's Name",
                              labelStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
                              filled: true,
                              fillColor: Colors.black.withOpacity(0.3),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                              prefixIcon: Icon(Icons.person, color: Colors.blue[400]),
                          ),
                        ),
                        
                        const SizedBox(height: 24),
                        
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: () async {
                              final name = nameController.text.trim();
                              if (name.isEmpty) {
                                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Please enter a name first")));
                                return;
                              }
                              Navigator.pop(context);
                              // Simple delay to let modal close before capturing
                              await Future.delayed(const Duration(milliseconds: 500));
                              await _performRegistration(name);
                            },
                            style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF3B82F6),
                                padding: const EdgeInsets.symmetric(vertical: 16),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))
                            ),
                            child: const Text("Capture & Register", style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                          ),
                        ),
                        // Extra space at bottom so button isn't immediately covered if keyboard is weird
                        const SizedBox(height: 48),
                    ],
                  ),
                ),
              ),
            );
          }
        );
      },
    );
  }

  Widget _buildInstructionItem(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: Colors.blue.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
            child: Icon(icon, color: Colors.blue[400], size: 20),
          ),
          const SizedBox(width: 16),
          Expanded(child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 15))),
        ],
      ),
    );
  }

  Future<void> _performRegistration(String name) async {
    setState(() => _statusMessage = "Registering...");
    final base64Image = await _captureAndEncode();
    
    if (base64Image == null) {
      setState(() => _statusMessage = "Capture failed");
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('$serverUrl/register'),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "name": name,
          "image": base64Image,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
            _statusMessage = data['message'] ?? "Registered Successfully";
            _statusColor = const Color(0xFF22C55E); // Green
        });
        await Future.delayed(const Duration(seconds: 2));
        setState(() => _statusMessage = "System Ready");
      } else {
         try {
           final data = jsonDecode(response.body);
           setState(() {
               _statusMessage = data['message'] ?? "Error: ${response.statusCode}";
               _statusColor = Colors.orange;
           });
         } catch (_) {
           setState(() => _statusMessage = "Error: ${response.statusCode}");
         }
      }
    } catch (e) {
      setState(() => _statusMessage = "Network Error");
    }
  }

  void _toggleScanning() {
    if (_isScanning) {
      _scanTimer?.cancel();
      setState(() {
        _isScanning = false;
        _statusMessage = "Monitoring Paused";
        _statusColor = Colors.grey;
        _detectedFaces = [];
        _detectedObjects = [];
        _detectedName = null;
      });
    } else {
      setState(() {
        _isScanning = true;
        _statusMessage = "Monitoring Active";
        _statusColor = const Color(0xFF3B82F6); // Blue
      });
      _scanTimer = Timer.periodic(const Duration(milliseconds: 300), (timer) {
        _performRecognition();
      });
    }
  }

  Future<void> _performRecognition() async {
    if (!_controller.value.isInitialized) return;
    
    final base64Image = await _captureAndEncode();
    if (base64Image == null) return;
    
    try {
      final response = await http.post(
        Uri.parse('$serverUrl/recognize'),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "image": base64Image,
        }),
      );

      if (response.statusCode == 200 && mounted) {
        final data = jsonDecode(response.body);
        final results = data['results'] as List<dynamic>? ?? [];
        final objects = data['objects'] as List<dynamic>? ?? [];
        final threatDetected = data['threat_detected'] ?? false;
        
        if (results.isNotEmpty || objects.isNotEmpty) {
             print("DEBUG Bounding Box: Received ${results.length} faces.");
             for (var r in results) {
                print("DEBUG Face: ${r['box']}");
             }
        } else {
             print("DEBUG Bounding Box: No faces received from server.");
        }
        
        List<Map<String, dynamic>> newFaces = [];
        List<Map<String, dynamic>> newObjects = [];
        String? priorityName; // For voice
        bool anyIntruder = false;
        bool anyBlink = false;
        
        // Process Voices & Faces
        for (var result in results) {
            final bool authorized = result['authorized'] ?? false;
            final String name = result['name'] ?? "Unknown";
            final box = result['box'];
            
            Color color;
            if (authorized) {
                color = const Color(0xFF22C55E); // Green
            } else if (name == "Blink to Verify") {
                color = Colors.orange;
                anyBlink = true;
            } else {
                color = const Color(0xFFEF4444); // Red
                anyIntruder = true;
            }
            
            if (box != null) {
                newFaces.add({
                    "rect": Rect.fromLTWH(
                         box['x'].toDouble(),
                         box['y'].toDouble(),
                         box['w'].toDouble(),
                         box['h'].toDouble(),
                    ),
                    "name": name,
                    "color": color,
                    "authorized": authorized
                });
            }
            
            // Priority for voice: Threat > Intruder > Blink > Authorized
            if (threatDetected) {
                priorityName = "Threat";
            } else if (!authorized && name != "Blink to Verify") {
                priorityName = "Intruder";
            } else if (name == "Blink to Verify" && priorityName != "Intruder" && priorityName != "Threat") {
                priorityName = "Blink";
            } else if (authorized && priorityName == null) {
                priorityName = name;
            }
        }
        
        // Process Objects
        for (var obj in objects) {
            final box = obj['box'];
            if (box != null) {
                 newObjects.add({
                    "rect": Rect.fromLTWH(
                         box['x'].toDouble(),
                         box['y'].toDouble(),
                         box['w'].toDouble(),
                         box['h'].toDouble(),
                    ),
                    "name": obj['name'],
                    "color": obj['is_threat'] ? Colors.redAccent : Colors.yellowAccent,
                 });
            }
        }

        // --- Voice Feedback Logic ---
        if (priorityName != null) {
            bool shouldReset = false;
            // Simplified logic: Just speak if different or after timeout
            if (priorityName != _lastSpokenName) {
                shouldReset = true;
            } else {
                 if (_lastSpeakTime != null && DateTime.now().difference(_lastSpeakTime!) > const Duration(seconds: 20)) {
                    shouldReset = true;
                }
            }
            
            if (shouldReset) {
                _speakCount = 0;
                _lastSpokenName = priorityName;
                _lastSpeakTime = null;
            }
            
             if (_speakCount < 1) {
                final now = DateTime.now();
                if (_lastSpeakTime == null || now.difference(_lastSpeakTime!) > const Duration(seconds: 3)) {
                    _lastSpeakTime = now;
                    _speakCount++;
                    
                    if (priorityName == "Threat") {
                        _speak("High Alert! Weapon Detected!");
                    } else if (priorityName == "Intruder") {
                        _speak("Warning! Intruder detected!");
                    } else if (priorityName == "Blink") {
                        _speak("Please blink to verify");
                    } else {
                        _speak("Welcome back, $priorityName");
                    }
                }
             }
        }

        setState(() {
           _detectedFaces = newFaces;
           _detectedObjects = newObjects;
           
           if (newFaces.isEmpty && newObjects.isEmpty) {
             if (_isScanning) {
                 _statusMessage = "Monitoring - No Activity";
                 _statusColor = const Color(0xFF3B82F6); // Blue
             }
             _detectedName = null;
           } else {
             if (threatDetected) {
                _statusColor = const Color(0xFFEF4444); // Red
                _statusMessage = "🚨 THREAT DETECTED 🚨";
                _detectedName = "Weapon/Threat Found";
             } else if (anyIntruder) {
                _statusColor = const Color(0xFFEF4444); // Red
                _statusMessage = "⚠️ INTRUDER ALERT ⚠️";
                _detectedName = "Intruder Detected";
             } else if (anyBlink) {
                _statusColor = Colors.orange;
                _statusMessage = "👁️ BLINK TO VERIFY";
                _detectedName = "Verifying...";
             } else {
                _statusColor = const Color(0xFF22C55E); // Green
                _statusMessage = "AUTHORIZED ACCESS";
                _detectedName = newFaces.map((f) => f['name']).join(", ");
             }
           }
        });
      }
    } catch (e) {
      print("Recognition error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
                // --- HEADER ---
                Container(
                  padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
                  decoration: const BoxDecoration(
                      color: Color(0xFF0F172A), // Use main BG
                      border: Border(bottom: BorderSide(color: Color(0xFF1E293B)))
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.shield_outlined, color: _statusColor, size: 28),
                      const SizedBox(width: 12),
                      Text(
                        "Home Security",
                        style: TextStyle(
                            fontSize: 20, 
                            fontWeight: FontWeight.bold, 
                            color: Colors.white.withOpacity(0.9)
                        ),
                      ),
                    ],
                  ),
                ),

                // --- CAMERA FEED ---
                Expanded(
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      FutureBuilder<void>(
                        future: _initializeControllerFuture,
                        builder: (context, snapshot) {
                          if (snapshot.connectionState == ConnectionState.done) {
                            return CameraPreview(_controller);
                          } else {
                            return const Center(child: CircularProgressIndicator());
                          }
                        },
                      ),
                      
                      // Bounding Box Overlay (Combined Faces + Objects)
                      CustomPaint(
                        painter: FacePainter(
                            faces: [..._detectedFaces, ..._detectedObjects], 
                        ),
                      ),

                      // Alert Banner for Intruder (Global Alert)
                      if (_statusColor == const Color(0xFFEF4444))
                        Positioned(
                            top: 20,
                            left: 20,
                            right: 20,
                            child: ClipRRect(
                                borderRadius: BorderRadius.circular(16),
                                child: BackdropFilter(
                                    filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                                    child: Container(
                                        padding: const EdgeInsets.all(16),
                                        decoration: BoxDecoration(
                                            color: const Color(0xFFEF4444).withOpacity(0.8),
                                            borderRadius: BorderRadius.circular(16),
                                            border: Border.all(color: Colors.white.withOpacity(0.2))
                                        ),
                                        child: Row(
                                            mainAxisAlignment: MainAxisAlignment.center,
                                            children: const [
                                                Icon(Icons.warning_amber_rounded, color: Colors.white, size: 30),
                                                SizedBox(width: 10),
                                                Text("INTRUDER DETECTED", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18))
                                            ],
                                        ),
                                    ),
                                )
                            ),
                        ),
                         
                      // Summary Widget (Top Left, below Intruder Alert if active)
                      Positioned(
                        top: 20, // push down a bit
                        left: 20,
                        child: _intruderCount > 0 ? ClipRRect(
                            borderRadius: BorderRadius.circular(20),
                            child: BackdropFilter(
                                filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
                                child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                    decoration: BoxDecoration(
                                        color: Colors.black.withOpacity(0.6),
                                        borderRadius: BorderRadius.circular(20),
                                        border: Border.all(color: Colors.white24)
                                    ),
                                    child: Row(
                                        children: [
                                            const Icon(Icons.history, color: Colors.white70, size: 16),
                                            const SizedBox(width: 8),
                                            Text("$_intruderCount Alerts Today", style: const TextStyle(color: Colors.white, fontSize: 12))
                                        ],
                                    ),
                                ),
                            )
                        ) : const SizedBox.shrink(),
                      ),
                    ],
                  ),
                ),

                // --- BOTTOM PANEL (Glassmorphism) ---
                ClipRRect(
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                    child: BackdropFilter(
                        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                        child: Container(
                            padding: const EdgeInsets.all(24),
                            decoration: BoxDecoration(
                                color: const Color(0xFF1E293B).withOpacity(0.9), // Slate 800 with opacity
                                borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                                border: Border(top: BorderSide(color: Colors.white.withOpacity(0.1)))
                            ),
                            child: Column(
                                children: [
                                    Container(
                                        width: 40, height: 4, 
                                        margin: const EdgeInsets.only(bottom: 20),
                                        decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(2))
                                    ),
                                    Text(
                                        _statusMessage.toUpperCase(),
                                        style: TextStyle(color: _statusColor, fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 1.5),
                                    ),
                                    const SizedBox(height: 24),
                                    Row(
                                        children: [
                                            Expanded(child: _buildControlButton(
                                                icon: Icons.person_add_rounded,
                                                label: "Register",
                                                color: const Color(0xFF3B82F6), // Blue
                                                onTap: _isScanning ? null : _registerUser
                                            )),
                                            const SizedBox(width: 12),
                                            Expanded(child: _buildControlButton(
                                                icon: _isScanning ? Icons.stop_rounded : Icons.play_arrow_rounded,
                                                label: _isScanning ? "Stop" : "Monitor",
                                                color: _isScanning ? const Color(0xFFEF4444) : const Color(0xFF22C55E), // Red/Green
                                                onTap: _toggleScanning,
                                                isPrimary: true
                                            )),
                                            const SizedBox(width: 12),
                                            Expanded(child: _buildControlButton(
                                                icon: Icons.history_rounded,
                                                label: "History",
                                                color: Colors.orangeAccent,
                                                onTap: _showHistory
                                            )),
                                            Expanded(child: _buildControlButton(
                                                icon: Icons.group_rounded,
                                                label: "Users",
                                                color: Colors.purpleAccent,
                                                onTap: _showAuthorizedUsers
                                            )),
                                            const SizedBox(width: 12),
                                            Expanded(child: _buildControlButton(
                                                icon: Icons.local_police_rounded,
                                                label: "PANIC",
                                                color: const Color(0xFFEF4444), // Red
                                                onTap: _triggerPanicMode,
                                                isPrimary: true
                                            )),
                                        ],
                                    )
                                ],
                            ),
                        ),
                    )
                ),
              ],
            ),
            
            // --- HIGH ALERT OVERLAY ---
            if (_isPanicMode)
              Positioned.fill(
                child: _buildPanicOverlay() // Correctly placed in Stack
              ),
          ],
        ),
      ),
    );
  }

  bool _isPanicMode = false;
  Timer? _strobeTimer;
  bool _strobeRed = true;
  int _panicCountdown = 5;

  Future<void> _triggerPanicMode() async {
      setState(() {
          _isPanicMode = true;
          _panicCountdown = 5;
      });
      _speak("High Alert Activated. Contacting Authorities in 5 seconds.");
      
      _strobeTimer?.cancel();
      _strobeTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
          if (mounted) {
              setState(() {
                  _strobeRed = !_strobeRed;
              });
          }
      });
      
      // Countdown Logic
      Timer.periodic(const Duration(seconds: 1), (timer) async {
          if (!_isPanicMode) {
              timer.cancel();
              return;
          }
          if (_panicCountdown > 0) {
              if (mounted) setState(() => _panicCountdown--);
          } else {
              timer.cancel();
              _speak("Calling Police Now.");
              final Uri phoneUri = Uri(scheme: 'tel', path: '100'); // INDIA POLICE
              if (await canLaunchUrl(phoneUri)) {
                  await launchUrl(phoneUri);
              } else {
                  print("Could not launch dialer");
              }
          }
      });
  }

  void _cancelPanicMode() {
      _strobeTimer?.cancel();
      setState(() {
          _isPanicMode = false;
      });
      _speak("Alert Cancelled. System returning to standby.");
  }

  Widget _buildPanicOverlay() {
      return Container(
          color: _strobeRed ? Colors.red.withOpacity(0.5) : Colors.blue.withOpacity(0.5), // Police Strobe
          child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
              child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                      const Icon(Icons.warning_amber_rounded, size: 100, color: Colors.white),
                      const SizedBox(height: 20),
                      const Text("HIGH ALERT", style: TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.bold, letterSpacing: 2.0)),
                      const SizedBox(height: 10),
                      Text("CONTACTING POLICE", style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 20, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 40),
                      
                      if (_panicCountdown > 0)
                        Container(
                            width: 120, height: 120,
                            decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white, width: 4)
                            ),
                            alignment: Alignment.center,
                            child: Text("$_panicCountdown", style: const TextStyle(color: Colors.white, fontSize: 60, fontWeight: FontWeight.bold))
                        )
                      else
                        Container(
                            padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 15),
                            decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(10)),
                            child: const Text("ALERT SENT", style: TextStyle(color: Colors.greenAccent, fontSize: 24, fontWeight: FontWeight.bold))
                        ),

                      const SizedBox(height: 60),
                      
                      SizedBox(
                          width: 250,
                          height: 60,
                          child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.white,
                                  foregroundColor: Colors.black,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30))
                              ),
                              onPressed: _cancelPanicMode,
                              child: const Text("CANCEL ALERT", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold))
                          )
                      ),
                  ],
              ),
          ),
      );
  }

  Future<List<dynamic>> _fetchHistory() async {
      try {
          final response = await http.get(Uri.parse('$serverUrl/api/history'));
          if (response.statusCode == 200) {
              final data = jsonDecode(response.body);
              return data['history'] ?? [];
          }
      } catch (e) {
          print("Error fetching history: $e");
      }
      return [];
  }

  Future<void> _deleteIntruder(int id, StateSetter setModalState) async {
      try {
          final response = await http.delete(Uri.parse('$serverUrl/api/intruders/$id'));
          if (response.statusCode == 200) {
              setModalState(() {}); // Trigger FutureBuilder rebuild
              _updateHistoryCount(); // Refresh general count
          } else {
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete intruder.')));
          }
      } catch (e) {
          print("Error deleting intruder: $e");
      }
  }

  void _showHistory() {
      showModalBottomSheet(
          context: context,
          backgroundColor: Colors.transparent, // For glass effect
          isScrollControlled: true,
          builder: (context) {
              return DraggableScrollableSheet(
                  initialChildSize: 0.6,
                  minChildSize: 0.4,
                  maxChildSize: 0.9,
                  builder: (_, controller) {
                      return ClipRRect(
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                          child: BackdropFilter(
                              filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                              child: Container(
                                  decoration: BoxDecoration(
                                      color: const Color(0xFF1E293B).withOpacity(0.95),
                                      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                                      border: Border(top: BorderSide(color: Colors.white.withOpacity(0.1)))
                                  ),
                                  child: FutureBuilder<List<dynamic>>(
                                      future: _fetchHistory(),
                                      builder: (context, snapshot) {
                                          if (snapshot.connectionState == ConnectionState.waiting) {
                                              return const Center(child: CircularProgressIndicator());
                                          }
                                          
                                          final history = snapshot.data ?? [];
                                          
                                          return Column(
                                              children: [
                                                  Container(
                                                      margin: const EdgeInsets.symmetric(vertical: 16),
                                                      width: 40, height: 4, 
                                                      decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(2))
                                                  ),
                                                  Padding(
                                                      padding: const EdgeInsets.only(bottom: 16),
                                                      child: Text("RECENT ACTIVITY", style: TextStyle(color: Colors.white.withOpacity(0.9), fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                                                  ),
                                                  Expanded(
                                                      child: history.isEmpty 
                                                          ? Center(child: Text("No recent activity", style: TextStyle(color: Colors.white.withOpacity(0.5))))
                                                          : ListView.builder(
                                                              controller: controller,
                                                              itemCount: history.length,
                                                              padding: const EdgeInsets.symmetric(horizontal: 20),
                                                              itemBuilder: (context, index) {
                                                                  final item = history[index];
                                                                  return Container(
                                                                    margin: const EdgeInsets.only(bottom: 12),
                                                                    decoration: BoxDecoration(
                                                                        color: Colors.black.withOpacity(0.2),
                                                                        borderRadius: BorderRadius.circular(12),
                                                                        border: Border.all(color: Colors.white.withOpacity(0.05))
                                                                    ),
                                                                    child: ListTile(
                                                                      leading: Container(
                                                                          padding: const EdgeInsets.all(8),
                                                                          decoration: BoxDecoration(
                                                                              color: const Color(0xFFEF4444).withOpacity(0.1),
                                                                              shape: BoxShape.circle
                                                                          ),
                                                                          child: const Icon(Icons.person_outline, color: Color(0xFFEF4444)),
                                                                      ),
                                                                      title: const Text("Intruder Detected", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                                                      subtitle: Text("${item['date']} at ${item['time']}", style: TextStyle(color: Colors.white.withOpacity(0.5))),
                                                                      trailing: IconButton(
                                                                        icon: const Icon(Icons.delete, color: Colors.grey),
                                                                        onPressed: () {
                                                                            _deleteIntruder(item['id'], (fn) {
                                                                                // Rebuild this modal's state to re-fetch FutureBuilder
                                                                                Navigator.pop(context); // simpler to just pop and reopen for now, or use StatefulBuilder
                                                                                _showHistory(); 
                                                                            });
                                                                        },
                                                                      ),
                                                                    ),
                                                                  );
                                                              },
                                                          ),
                                                  ),
                                              ],
                                          );
                                      }
                                  ),
                              ),
                          )
                      );
                  }
              );
          }
      );
  }

  Future<List<dynamic>> _fetchAuthorizedUsers() async {
      try {
          final response = await http.get(Uri.parse('$serverUrl/api/authorized'));
          if (response.statusCode == 200) {
              final data = jsonDecode(response.body);
              return data['users'] ?? [];
          }
      } catch (e) {
          print("Error fetching users: $e");
      }
      return [];
  }

  Future<void> _deleteAuthorizedUser(int id, StateSetter setModalState) async {
      try {
          final response = await http.delete(Uri.parse('$serverUrl/api/authorized/$id'));
          if (response.statusCode == 200) {
              setModalState(() {}); 
          } else {
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete user.')));
          }
      } catch (e) {
          print("Error deleting user: $e");
      }
  }

  void _showAuthorizedUsers() {
      showModalBottomSheet(
          context: context,
          backgroundColor: Colors.transparent, 
          isScrollControlled: true,
          builder: (context) {
              return StatefulBuilder(
                  builder: (BuildContext context, StateSetter setModalState) {
                      return DraggableScrollableSheet(
                          initialChildSize: 0.6,
                          minChildSize: 0.4,
                          maxChildSize: 0.9,
                          builder: (_, controller) {
                              return ClipRRect(
                                  borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                                  child: BackdropFilter(
                                      filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                                      child: Container(
                                          decoration: BoxDecoration(
                                              color: const Color(0xFF1E293B).withOpacity(0.95),
                                              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                                              border: Border(top: BorderSide(color: Colors.white.withOpacity(0.1)))
                                          ),
                                          child: FutureBuilder<List<dynamic>>(
                                              future: _fetchAuthorizedUsers(),
                                              builder: (context, snapshot) {
                                                  if (snapshot.connectionState == ConnectionState.waiting) {
                                                      return const Center(child: CircularProgressIndicator());
                                                  }
                                                  
                                                  final users = snapshot.data ?? [];
                                                  
                                                  return Column(
                                                      children: [
                                                          Container(
                                                              margin: const EdgeInsets.symmetric(vertical: 16),
                                                              width: 40, height: 4, 
                                                              decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(2))
                                                          ),
                                                          Padding(
                                                              padding: const EdgeInsets.only(bottom: 16),
                                                              child: Text("AUTHORIZED USERS", style: TextStyle(color: Colors.white.withOpacity(0.9), fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                                                          ),
                                                          Expanded(
                                                              child: users.isEmpty 
                                                                  ? Center(child: Text("No authorized users", style: TextStyle(color: Colors.white.withOpacity(0.5))))
                                                                  : ListView.builder(
                                                                      controller: controller,
                                                                      itemCount: users.length,
                                                                      padding: const EdgeInsets.symmetric(horizontal: 20),
                                                                      itemBuilder: (context, index) {
                                                                          final user = users[index];
                                                                          return Container(
                                                                            margin: const EdgeInsets.only(bottom: 12),
                                                                            decoration: BoxDecoration(
                                                                                color: Colors.black.withOpacity(0.2),
                                                                                borderRadius: BorderRadius.circular(12),
                                                                                border: Border.all(color: Colors.white.withOpacity(0.05))
                                                                            ),
                                                                            child: ListTile(
                                                                              leading: Container(
                                                                                  padding: const EdgeInsets.all(8),
                                                                                  decoration: BoxDecoration(
                                                                                      color: const Color(0xFF22C55E).withOpacity(0.1),
                                                                                      shape: BoxShape.circle
                                                                                  ),
                                                                                  child: const Icon(Icons.person, color: Color(0xFF22C55E)),
                                                                              ),
                                                                              title: Text(user['name'] ?? "Unknown", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                                                              subtitle: Text("Registered: ${user['registered_at'] ?? 'Unknown'}", style: TextStyle(color: Colors.white.withOpacity(0.5))),
                                                                              trailing: IconButton(
                                                                                icon: const Icon(Icons.delete, color: Colors.grey),
                                                                                onPressed: () {
                                                                                    _deleteAuthorizedUser(user['id'], setModalState);
                                                                                },
                                                                              ),
                                                                            ),
                                                                          );
                                                                      },
                                                                  ),
                                                          ),
                                                      ],
                                                  );
                                              }
                                          ),
                                      ),
                                  )
                              );
                          }
                      );
                  }
              );
          }
      );
  }

  Widget _buildControlButton({
      required IconData icon, 
      required String label, 
      required Color color, 
      required VoidCallback? onTap,
      bool isPrimary = false
  }) {
      final isActive = onTap != null;
      return Material(
          color: Colors.transparent,
          child: InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(16),
              child: Ink(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                      color: isPrimary && isActive 
                          ? color 
                          : (isActive ? color.withOpacity(0.15) : Colors.white.withOpacity(0.05)),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                          color: isPrimary && isActive ? Colors.transparent : (isActive ? color.withOpacity(0.3) : Colors.white.withOpacity(0.1))
                      ),
                      boxShadow: isPrimary && isActive ? [
                          BoxShadow(color: color.withOpacity(0.4), blurRadius: 10, offset: const Offset(0, 4))
                      ] : null
                  ),
                  child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                          Icon(icon, color: isPrimary && isActive ? Colors.white : (isActive ? color : Colors.grey), size: 26),
                          const SizedBox(height: 8),
                          Text(label, style: TextStyle(
                              color: isPrimary && isActive ? Colors.white : (isActive ? color : Colors.grey), 
                              fontWeight: FontWeight.w600, 
                              fontSize: 13
                          ))
                      ],
                  ),
              ),
          ),
      );
  }
}

class FacePainter extends CustomPainter {
  final List<Map<String, dynamic>> faces;

  FacePainter({required this.faces});

  @override
  void paint(Canvas canvas, Size size) {
    if (faces.isEmpty) return;

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
      
    final fillPaint = Paint()
      ..style = PaintingStyle.fill;

    for (var face in faces) {
        final rectRaw = face['rect'] as Rect;
        final color = face['color'] as Color;
        final name = face['name'] as String;
        
        paint.color = color;
        fillPaint.color = color.withOpacity(0.15); // Lighter fill

        final rect = Rect.fromLTWH(
          rectRaw.left * size.width,
          rectRaw.top * size.height,
          rectRaw.width * size.width,
          rectRaw.height * size.height,
        );
        
        // Draw Rounded Box (Cyberpunk Corners)
        final double cornerSize = 20.0;
        final path = Path();
        
        // Top Left
        path.moveTo(rect.left, rect.top + cornerSize);
        path.lineTo(rect.left, rect.top);
        path.lineTo(rect.left + cornerSize, rect.top);
        
        // Top Right
        path.moveTo(rect.right - cornerSize, rect.top);
        path.lineTo(rect.right, rect.top);
        path.lineTo(rect.right, rect.top + cornerSize);
        
        // Bottom Right
        path.moveTo(rect.right, rect.bottom - cornerSize);
        path.lineTo(rect.right, rect.bottom);
        path.lineTo(rect.right - cornerSize, rect.bottom);
        
        // Bottom Left
        path.moveTo(rect.left + cornerSize, rect.bottom);
        path.lineTo(rect.left, rect.bottom);
        path.lineTo(rect.left, rect.bottom - cornerSize);
        
        canvas.drawPath(path, Paint()..color = color ..style = PaintingStyle.stroke ..strokeWidth = 3.0 ..strokeCap = StrokeCap.square);
        
        // Inner thin box
        canvas.drawRect(rect, Paint()..color = color.withOpacity(0.5) ..style = PaintingStyle.stroke ..strokeWidth = 1.0);
        canvas.drawRect(rect, fillPaint);
        
        if (name != "No Face") {
            final textSpan = TextSpan(
                text: name.toUpperCase(),
                style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.0),
            );
            final textPainter = TextPainter(
                text: textSpan,
                textDirection: TextDirection.ltr,
            );
            textPainter.layout();
            
            final textBgRect = Rect.fromLTWH(
                rect.left,
                rect.top - 24, 
                textPainter.width + 16,
                24,
            );
            
            Offset textOffset;
            if (textBgRect.top < 0) {
                 textOffset = Offset(rect.left + 8, rect.top + 5);
                 canvas.drawRect(
                     Rect.fromLTWH(rect.left, rect.top, textPainter.width + 16, 24), 
                     Paint()..color = color
                 );
            } else {
                 textOffset = Offset(rect.left + 8, rect.top - 20);
                 canvas.drawRect(textBgRect, Paint()..color = color);
            }

            textPainter.paint(canvas, textOffset);
        }
    }
  }

  @override
  bool shouldRepaint(FacePainter oldDelegate) => true;
}
