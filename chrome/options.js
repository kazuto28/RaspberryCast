function saveSettings() {
	localStorage.raspip = document.getElementById("raspip").value;
	localStorage.rasport = document.getElementById("rasport").value;
	alert("Settings were successfully saved !");
}

document.addEventListener("DOMContentLoaded", function() {
	if (localStorage.raspip != undefined) {
		document.getElementById("raspip").value = localStorage.raspip;
		
	}

	if (localStorage.rasport == undefined) {
		localStorage.rasport = "2020";
		document.getElementById("rasport").value = localStorage.rasport;
	} else {
		document.getElementById("rasport").value = localStorage.rasport;
	}

	var el;
	el = document.getElementById("saveButton");
	el.addEventListener("click", saveSettings, false);
});
