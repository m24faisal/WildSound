package com.example.wildsound

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.ripple
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.wildsound.ui.theme.WildSoundTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            WildSoundTheme {
                WildSoundApp()
            }
        }
    }
}

@Composable
fun WildSoundApp() {
    // Track which bottom nav item is selected
    var selectedItem by remember { mutableIntStateOf(0) }

    // List of bottom nav items
    val items = listOf(
        BottomNavItem.Home,
        BottomNavItem.Library,
        BottomNavItem.Settings
    )

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = { WildSoundTopBar() },
        bottomBar = {
            NavigationBar {
                items.forEachIndexed { index, item ->
                    NavigationBarItem(
                        selected = selectedItem == index,
                        onClick = { selectedItem = index },
                        icon = {
                            Icon(
                                imageVector = item.icon,
                                contentDescription = item.title
                            )
                        },
                        label = {
                            Text(text = item.title)
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        // Content area that changes based on selected tab
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (selectedItem) {
                0 -> HomeScreen()
                1 -> LibraryScreen()
                2 -> SettingsScreen()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WildSoundTopBar() {
    TopAppBar(
        title = {
            Text(
                text = "Wild Sound",
                color = Color.White,
                fontSize = 20.sp
            )
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = Color(0xFF2E7D32),
            titleContentColor = Color.White
        )
    )
}

@Composable
fun HomeScreen() {
    // State to track if we're in "listening" mode
    var isListening by remember { mutableStateOf(false) }

    // Permission state
    var showPermissionDialog by remember { mutableStateOf(false) }
    var isPermanentlyDenied by remember { mutableStateOf(false) }
    val context = LocalContext.current

    // Check if permission is already granted
    val isPermissionGranted = remember {
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    // Permission launcher
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            // Permission granted - start listening
            isListening = true
        } else {
            // Check if permanently denied with API level check
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val activity = context as ComponentActivity
                isPermanentlyDenied = !activity.shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO)
            } else {
                // Below API 23, permissions are granted at install time
                isPermanentlyDenied = false
            }
            showPermissionDialog = true
        }
    }

    // Create and remember the interaction source for ripple effect
    val interactionSource = remember { MutableInteractionSource() }

    // Animation for the pulsing effect (idle state)
    val infiniteTransition = rememberInfiniteTransition()
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        )
    )

    // Animation for the wave emission effect (listening state)
    val waveTransition = rememberInfiniteTransition()
    val waveScale by waveTransition.animateFloat(
        initialValue = 1f,
        targetValue = 2.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = FastOutLinearInEasing)
        )
    )
    val waveAlpha by waveTransition.animateFloat(
        initialValue = 0.7f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = FastOutLinearInEasing)
        )
    )

    Box(
        modifier = Modifier.fillMaxSize()
    ) {
        // Exit button (X) - only visible when listening
        if (isListening) {
            IconButton(
                onClick = {
                    isListening = false
                },
                modifier = Modifier
                    .padding(16.dp)
                    .size(48.dp)
                    .align(Alignment.TopStart)
                    .background(Color(0xFF2E7D32).copy(alpha = 0.2f), CircleShape)
                    .clip(CircleShape)
            ) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Stop Listening",
                    tint = Color(0xFF2E7D32),
                    modifier = Modifier.size(24.dp)
                )
            }
        }

        // Main content centered
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Message above the button - REMOVED the microphone required message
            Text(
                text = if (isListening) "Listening..." else "Tap to go Wild!",
                color = Color(0xFF2E7D32),
                fontSize = 20.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(bottom = 32.dp)
            )

            // Container for button and waves
            Box(
                contentAlignment = Alignment.Center
            ) {
                // Wave emission rings (only visible when listening)
                if (isListening) {
                    // Use the animation values
                    val currentWaveScale = waveScale
                    val currentWaveAlpha = waveAlpha

                    // Multiple rings for richer effect
                    for (i in 0..2) {
                        Box(
                            modifier = Modifier
                                .size(150.dp * (1f + i * 0.3f))
                                .scale(currentWaveScale - (i * 0.3f))
                                .clip(CircleShape)
                                .background(
                                    Color(0xFF2E7D32).copy(
                                        alpha = currentWaveAlpha * (1f - i * 0.2f)
                                    )
                                )
                        )
                    }
                }

                // Main clickable button
                Box(
                    modifier = Modifier
                        .scale(if (isListening) 1f else pulseScale)
                        .clip(CircleShape)
                        .clickable(
                            interactionSource = interactionSource,
                            indication = ripple(
                                color = Color.White,
                                bounded = true
                            )
                        ) {
                            // Handle button click with permission check
                            if (!isListening) {
                                if (isPermissionGranted) {
                                    // Permission already granted - start listening
                                    isListening = true
                                } else {
                                    // Need to request permission first
                                    permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                }
                            }
                        },
                    contentAlignment = Alignment.Center
                ) {
                    // Green circle background
                    Box(
                        modifier = Modifier
                            .size(150.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF2E7D32))
                    )

                    // Logo on top
                    Image(
                        painter = painterResource(id = R.drawable.logo),
                        contentDescription = "Wild Sound Logo",
                        modifier = Modifier.size(100.dp)
                    )
                }
            }
        }
    }

    // Permission dialog
    if (showPermissionDialog) {
        AlertDialog(
            onDismissRequest = {
                showPermissionDialog = false
            },
            title = {
                Text(text = "Microphone Permission Required")
            },
            text = {
                Text(
                    text = if (isPermanentlyDenied) {
                        "Microphone permission is permanently denied. Please enable it in app settings to use Wild Sound."
                    } else {
                        "Wild Sound needs microphone access to listen and identify music around you."
                    }
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showPermissionDialog = false
                        if (isPermanentlyDenied) {
                            // Open app settings
                            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                                data = Uri.fromParts("package", context.packageName, null)
                            }
                            context.startActivity(intent)
                        } else {
                            // Request permission again
                            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    }
                ) {
                    Text(text = if (isPermanentlyDenied) "Open Settings" else "Request Permission")
                }
            },
            dismissButton = {
                Button(
                    onClick = {
                        showPermissionDialog = false
                    }
                ) {
                    Text(text = "Cancel")
                }
            }
        )
    }
}

@Composable
fun LibraryScreen() {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "Library Screen",
            fontSize = 20.sp
        )
    }
}

@Composable
fun SettingsScreen() {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "Settings Screen",
            fontSize = 20.sp
        )
    }
}

// Data class for bottom navigation items using built-in icons
sealed class BottomNavItem(val title: String, val icon: ImageVector) {
    data object Home : BottomNavItem("Home", Icons.Default.Home)
    data object Library : BottomNavItem("Database", Icons.Default.Menu)
    data object Settings : BottomNavItem("Settings", Icons.Default.Settings)
}