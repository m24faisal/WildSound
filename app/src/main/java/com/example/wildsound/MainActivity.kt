package com.example.wildsound

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.util.Log
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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

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

// Data class for animal sound results from iNaturalist
data class AnimalSoundResult(
    val speciesName: String,
    val commonName: String,
    val scientificName: String,
    val audioUrl: String,
    val observationId: String,
    val observer: String,
    val observedDate: String,
    val license: String,
    val qualityGrade: String
)

// API Service for iNaturalist
object INaturalistService {
    private const val BASE_URL = "https://api.inaturalist.org/v1"
    private const val USER_AGENT = "WildSoundApp/1.0 (Android)"

    /**
     * Search for animal sounds by common name or scientific name
     */
    suspend fun searchAnimalSounds(query: String): List<AnimalSoundResult> = withContext(Dispatchers.IO) {
        val results = mutableListOf<AnimalSoundResult>()

        try {
            // Step 1: Search for taxa matching the query
            val taxonUrl = "$BASE_URL/taxa?q=${query.replace(" ", "%20")}&per_page=5"
            Log.d("INatAPI", "Searching taxa: $taxonUrl")

            val taxonResponse = makeGetRequest(taxonUrl)
            val taxonJson = JSONObject(taxonResponse)
            val taxonResults = taxonJson.getJSONArray("results")

            val taxonIds = mutableListOf<Int>()
            for (i in 0 until taxonResults.length()) {
                val taxon = taxonResults.getJSONObject(i)
                val taxonId = taxon.getInt("id")
                taxonIds.add(taxonId)
            }

            // Step 2: For each taxon, get observations with sounds
            for (taxonId in taxonIds) {
                val obsUrl = "$BASE_URL/observations?" +
                        "taxon_id=$taxonId&" +
                        "has[]=sounds&" +
                        "verifiable=true&" +
                        "per_page=20"

                Log.d("INatAPI", "Searching observations: $obsUrl")

                val obsResponse = makeGetRequest(obsUrl)
                val obsJson = JSONObject(obsResponse)
                val obsResults = obsJson.getJSONArray("results")

                for (j in 0 until obsResults.length()) {
                    val observation = obsResults.getJSONObject(j)

                    // Extract taxon information
                    val taxon = observation.getJSONObject("taxon")
                    val scientificName = taxon.getString("name")
                    val commonName = if (taxon.has("preferred_common_name")) {
                        taxon.getString("preferred_common_name")
                    } else {
                        taxon.optString("english_common_name", scientificName)
                    }

                    // Get sounds array
                    val sounds = observation.optJSONArray("sounds")
                    if (sounds != null) {
                        for (k in 0 until sounds.length()) {
                            val sound = sounds.getJSONObject(k)
                            val fileUrl = sound.optString("file_url")

                            if (fileUrl.isNotEmpty()) {
                                // Convert HTTP to HTTPS if needed
                                val secureUrl = fileUrl.replace("http://", "https://")

                                val result = AnimalSoundResult(
                                    speciesName = commonName,
                                    commonName = commonName,
                                    scientificName = scientificName,
                                    audioUrl = secureUrl,
                                    observationId = observation.getString("id"),
                                    observer = observation.getJSONObject("user").getString("login"),
                                    observedDate = observation.optString("observed_on", "Unknown date"),
                                    license = sound.optString("license_code", "Unknown license"),
                                    qualityGrade = observation.getString("quality_grade")
                                )
                                results.add(result)
                            }
                        }
                    }
                }
            }

            // Limit to 30 results to avoid overwhelming the UI
            results.take(30)

        } catch (e: Exception) {
            Log.e("INatAPI", "Error searching iNaturalist", e)
            emptyList()
        }
    }

    /**
     * Search for sounds by specific animal type
     */
    suspend fun searchByAnimalType(animalType: String): List<AnimalSoundResult> {
        val commonSearches = mapOf(
            "dog" to "Canis lupus familiaris",
            "cat" to "Felis catus",
            "lion" to "Panthera leo",
            "tiger" to "Panthera tigris",
            "bear" to "Ursus",
            "wolf" to "Canis lupus",
            "fox" to "Vulpes",
            "elephant" to "Elephantidae",
            "bird" to "Aves",
            "frog" to "Anura"
        )

        val searchQuery = commonSearches[animalType.lowercase()] ?: animalType
        return searchAnimalSounds(searchQuery)
    }

    /**
     * Download an audio file from iNaturalist
     */
    suspend fun downloadAnimalSound(
        result: AnimalSoundResult,
        outputFile: File
    ): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL(result.audioUrl)
            val connection = url.openConnection() as HttpURLConnection
            connection.setRequestProperty("User-Agent", USER_AGENT)
            connection.connect()

            connection.inputStream.use { input ->
                FileOutputStream(outputFile).use { output ->
                    input.copyTo(output)
                }
            }

            Log.d("INatAPI", "Downloaded: ${outputFile.absolutePath}")
            true
        } catch (e: Exception) {
            Log.e("INatAPI", "Download failed", e)
            false
        }
    }

    private fun makeGetRequest(urlString: String): String {
        val url = URL(urlString)
        val connection = url.openConnection() as HttpURLConnection
        connection.setRequestProperty("User-Agent", USER_AGENT)
        connection.setRequestProperty("Accept", "application/json")
        connection.connectTimeout = 10000
        connection.readTimeout = 10000

        return connection.inputStream.bufferedReader().use { it.readText() }
    }
}

@Composable
fun HomeScreen() {
    // State to track if we're in "listening" mode
    var isListening by remember { mutableStateOf(false) }

    // Permission state
    var showPermissionDialog by remember { mutableStateOf(false) }
    var isPermanentlyDenied by remember { mutableStateOf(false) }
    val context = LocalContext.current

    // iNaturalist API states
    var isSearching by remember { mutableStateOf(false) }
    var searchResults by remember { mutableStateOf<List<AnimalSoundResult>>(emptyList()) }
    var searchError by remember { mutableStateOf<String?>(null) }
    var selectedAnimalType by remember { mutableStateOf("dog") }
    var downloadedSounds by remember { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    var isDownloading by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableStateOf(0f) }

    // Coroutine scope for background tasks
    val coroutineScope = rememberCoroutineScope()

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

        // Main content
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Animal type selector
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                AnimalTypeChip(
                    name = "Dog",
                    isSelected = selectedAnimalType == "dog",
                    onSelected = { selectedAnimalType = "dog" }
                )
                AnimalTypeChip(
                    name = "Cat",
                    isSelected = selectedAnimalType == "cat",
                    onSelected = { selectedAnimalType = "cat" }
                )
                AnimalTypeChip(
                    name = "Bird",
                    isSelected = selectedAnimalType == "bird",
                    onSelected = { selectedAnimalType = "bird" }
                )
                AnimalTypeChip(
                    name = "Lion",
                    isSelected = selectedAnimalType == "lion",
                    onSelected = { selectedAnimalType = "lion" }
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Message above the button
            Text(
                text = if (isListening) "Listening..." else "Tap to find animal sounds!",
                color = Color(0xFF2E7D32),
                fontSize = 20.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(bottom = 16.dp)
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
                                    // Search for animal sounds
                                    if (selectedAnimalType.isNotEmpty()) {
                                        coroutineScope.launch {
                                            isSearching = true
                                            searchError = null
                                            try {
                                                searchResults = INaturalistService.searchByAnimalType(selectedAnimalType)
                                            } catch (e: Exception) {
                                                searchError = e.message
                                            } finally {
                                                isSearching = false
                                            }
                                        }
                                    }
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

            // Search status
            if (isSearching) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    CircularProgressIndicator(
                        color = Color(0xFF2E7D32)
                    )
                    Text(
                        text = "Searching iNaturalist database...",
                        fontSize = 14.sp,
                        color = Color.Gray,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }
            }

            // Search results
            if (searchResults.isNotEmpty()) {
                Text(
                    text = "Found ${searchResults.size} recordings:",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF2E7D32),
                    modifier = Modifier
                        .align(Alignment.Start)
                        .padding(top = 24.dp, bottom = 8.dp)
                )

                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                ) {
                    items(searchResults) { result ->
                        INaturalistResultCard(
                            result = result,
                            onDownload = {
                                coroutineScope.launch {
                                    isDownloading = true
                                    downloadProgress = 0f
                                    try {
                                        val fileName = "${result.scientificName.replace(" ", "_")}_${result.observationId}.mp3"
                                        val outputFile = File(context.getExternalFilesDir("animal_sounds"), fileName)

                                        downloadProgress = 0.3f
                                        val success = INaturalistService.downloadAnimalSound(result, outputFile)
                                        downloadProgress = if (success) 1f else 0f

                                        if (success) {
                                            downloadedSounds = downloadedSounds + (result.commonName to outputFile.absolutePath)
                                        } else {
                                            searchError = "Download failed"
                                        }
                                        delay(500)
                                    } catch (e: Exception) {
                                        searchError = "Download failed: ${e.message}"
                                    } finally {
                                        isDownloading = false
                                        downloadProgress = 0f
                                    }
                                }
                            }
                        )
                    }
                }
            }

            // Download progress
            if (isDownloading) {
                LinearProgressIndicator(
                    progress = { downloadProgress },
                    modifier = Modifier
                        .fillMaxWidth(0.7f)
                        .padding(top = 16.dp),
                    color = Color(0xFF2E7D32)
                )
            }

            // Downloaded sounds list
            if (downloadedSounds.isNotEmpty()) {
                Text(
                    text = "Downloaded Sounds:",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .align(Alignment.Start)
                        .padding(top = 16.dp)
                )

                downloadedSounds.takeLast(3).forEach { (species, path) ->
                    Text(
                        text = "✓ $species",
                        fontSize = 14.sp,
                        color = Color(0xFF2E7D32),
                        modifier = Modifier
                            .align(Alignment.Start)
                            .padding(start = 8.dp, top = 4.dp)
                    )
                }
            }

            // Error message
            if (searchError != null) {
                Text(
                    text = "Error: $searchError",
                    color = Color.Red,
                    fontSize = 14.sp,
                    modifier = Modifier.padding(top = 16.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
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
                        "Wild Sound needs microphone access to listen and identify animal sounds around you."
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
fun AnimalTypeChip(
    name: String,
    isSelected: Boolean,
    onSelected: () -> Unit
) {
    Card(
        modifier = Modifier
            .size(70.dp, 40.dp)
            .clickable { onSelected() },
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) Color(0xFF2E7D32) else Color(0xFFE0E0E0)
        ),
        shape = RoundedCornerShape(20.dp)
    ) {
        Box(
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = name,
                color = if (isSelected) Color.White else Color.Black,
                fontSize = 14.sp,
                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
            )
        }
    }
}

@Composable
fun INaturalistResultCard(
    result: AnimalSoundResult,
    onDownload: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFF5F5F5)
        ),
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp)
        ) {
            Text(
                text = result.commonName,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = result.scientificName,
                fontSize = 14.sp,
                color = Color.Gray
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "By: ${result.observer}",
                        fontSize = 12.sp,
                        color = Color.DarkGray
                    )
                    Text(
                        text = "Date: ${result.observedDate.take(10)}",
                        fontSize = 12.sp,
                        color = Color.DarkGray
                    )
                }

                Button(
                    onClick = onDownload,
                    modifier = Modifier.size(80.dp, 36.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF2E7D32)
                    )
                ) {
                    Text("Save", fontSize = 12.sp)
                }
            }

            Text(
                text = "License: ${result.license}",
                fontSize = 10.sp,
                color = Color.LightGray,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
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