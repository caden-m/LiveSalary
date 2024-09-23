document.addEventListener('DOMContentLoaded', function () {
    const startStopBtn = document.getElementById('startStopBtn');
    const resetBtn = document.getElementById('resetBtn');
    const earningsDisplay = document.getElementById('earnings');
    const hoursDisplay = document.getElementById('hours');
    const minutesDisplay = document.getElementById('minutes');
    const secondsDisplay = document.getElementById('seconds');
    const amPmDisplay = document.getElementById('amPm');
    const dateDisplay = document.getElementById('dateDisplay');
    const toggleRateBtn = document.getElementById('toggleRateBtn');
    const rateInput = document.getElementById('hourlyRate');
    const validationMessage = document.getElementById('validationMessage');

    let isTimerRunning = false;
    let startTime;
    let totalEarnings = 0;
    let hourlyRate = 0;
    let totalElapsedTime = 0;

    function pad(number) {
        return number < 10 ? '0' + number : number;
    }

    function updateClock() {
        const now = new Date();
        let hours = now.getHours();
        let minutes = now.getMinutes();
        let seconds = now.getSeconds();
        const amPm = hours >= 12 ? 'PM' : 'AM';

        hours = hours % 12 || 12;

        hoursDisplay.textContent = pad(hours);
        minutesDisplay.textContent = pad(minutes);
        secondsDisplay.textContent = pad(seconds);
        amPmDisplay.textContent = amPm;

        const dayOfWeek = now.toLocaleString('default', { weekday: 'long' });
        const month = now.toLocaleString('default', { month: 'long' });
        const day = now.getDate();

        dateDisplay.textContent = `${dayOfWeek}, ${day} ${month}`;
    }

    setInterval(updateClock, 1000);
    updateClock(); // Initial call to display time immediately

    function startTimer() {
        hourlyRate = parseFloat(rateInput.value);
        if (isNaN(hourlyRate) || hourlyRate <= 0) {
            validationMessage.textContent = 'Please enter a valid hourly rate.';
            return;
        } else {
            validationMessage.textContent = '';
        }

        if (!isTimerRunning) {
            startEarningsTimer();
            startStopBtn.textContent = 'Pause';
            isTimerRunning = true;
        } else {
            stopEarningsTimer();
            startStopBtn.textContent = 'Start';
            isTimerRunning = false;
        }
    }

    function resetTimer() {
        stopEarningsTimer();
        totalEarnings = 0;
        totalElapsedTime = 0;
        earningsDisplay.textContent = `Earnings: $0.00`;
        startStopBtn.textContent = 'Start';
        isTimerRunning = false;
    }

    function startEarningsTimer() {
        startTime = Date.now() - totalElapsedTime;
        isTimerRunning = true;

        function updateEarnings() {
            if (!isTimerRunning) return;
            totalElapsedTime = Date.now() - startTime;
            let elapsedHours = totalElapsedTime / 3600000;
            totalEarnings = hourlyRate * elapsedHours;
            earningsDisplay.textContent = `Earnings: $${totalEarnings.toFixed(2)}`;
            requestAnimationFrame(updateEarnings);
        }

        requestAnimationFrame(updateEarnings);
    }

    function stopEarningsTimer() {
        isTimerRunning = false;
    }

    function toggleRateVisibility() {
        if (rateInput.type === 'text') {
            rateInput.type = 'password';
            toggleRateBtn.textContent = 'Show Rate';
        } else {
            rateInput.type = 'text';
            toggleRateBtn.textContent = 'Hide Rate';
        }
    }

    // Enforce numeric input with decimals
    rateInput.addEventListener('input', function () {
        // Remove any characters that are not digits or a decimal point
        rateInput.value = rateInput.value.replace(/[^\d.]/g, '');

        // Ensure only one decimal point is present
        if ((rateInput.value.match(/\./g) || []).length > 1) {
            rateInput.value = rateInput.value.slice(0, -1);
        }
    });

    startStopBtn.addEventListener('click', startTimer);
    resetBtn.addEventListener('click', resetTimer);
    toggleRateBtn.addEventListener('click', toggleRateVisibility);
});




