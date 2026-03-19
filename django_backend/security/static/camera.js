const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusDiv = document.getElementById("status");

const ctx = canvas.getContext("2d");

// 1️⃣ Start camera
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => video.srcObject = stream)
  .catch(err => alert("Camera error: " + err));

// 2️⃣ Capture frame
function captureFrame() {
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg");
}

// 3️⃣ Send frame to backend
function recognize() {
  fetch("/api/recognize/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image: captureFrame()
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.authorized) {
      statusDiv.innerText = "AUTHORIZED : " + data.name;
      statusDiv.className = "authorized";
    } else {
      statusDiv.innerText = "UNAUTHORIZED";
      statusDiv.className = "unauthorized";
    }
  })
  .catch(err => console.error(err));
}

// 4️⃣ Run recognition every 1 second
setInterval(recognize, 1000);
