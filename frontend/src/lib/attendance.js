const STORAGE_KEY = 'ems_attendance_records';

export const WORK_HOURS = {
  START: '09:00',
  END: '17:00', // 5:00 PM
};

export const ATTENDANCE_STATUS = {
  PRESENT: 'PRESENT',          // Green
  EARLY_LOGOFF: 'EARLY_LOGOFF', // Yellow (logged off before 5:00 PM)
  ABSENT: 'ABSENT',            // Red
  NOT_MARKED: 'NOT_MARKED',    // Muted Gray
};

function getStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    return {};
  }
}

function setStorage(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (err) {
    // Ignore storage quota errors
  }
}

export function formatTime(dateObj = new Date()) {
  let hours = dateObj.getHours();
  const minutes = dateObj.getMinutes();
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12; // hour 0 is 12
  const strMinutes = minutes < 10 ? '0' + minutes : minutes;
  return `${hours}:${strMinutes} ${ampm}`;
}

export function getTodayDateString(dateObj = new Date()) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, '0');
  const d = String(dateObj.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function getAttendanceRecords(userId) {
  if (!userId) return [];
  const store = getStorage();
  return store[userId] || [];
}

export function getAttendanceForDate(userId, targetDate) {
  if (!userId || !targetDate) return null;
  const records = getAttendanceRecords(userId);
  return records.find((r) => r.date === targetDate) || null;
}

export function getTodayStatus(userId) {
  const records = getAttendanceRecords(userId);
  const todayStr = getTodayDateString();
  return records.find((r) => r.date === todayStr) || null;
}

export function clockIn(userId, customTime = null) {
  if (!userId) return null;
  const store = getStorage();
  const userRecords = store[userId] || [];
  const todayStr = getTodayDateString();

  let todayRecord = userRecords.find((r) => r.date === todayStr);
  const nowStr = customTime || formatTime();

  if (!todayRecord) {
    todayRecord = {
      date: todayStr,
      clockIn: nowStr,
      clockOut: null,
      status: ATTENDANCE_STATUS.PRESENT,
    };
    userRecords.push(todayRecord);
  } else if (!todayRecord.clockIn) {
    todayRecord.clockIn = nowStr;
  }

  store[userId] = userRecords;
  setStorage(store);
  return todayRecord;
}

export function clockOut(userId, customTime = null, customHour = null) {
  if (!userId) return null;
  const store = getStorage();
  const userRecords = store[userId] || [];
  const todayStr = getTodayDateString();

  let todayRecord = userRecords.find((r) => r.date === todayStr);
  if (!todayRecord) {
    todayRecord = {
      date: todayStr,
      clockIn: '09:00 AM',
      clockOut: null,
      status: ATTENDANCE_STATUS.PRESENT,
    };
    userRecords.push(todayRecord);
  }

  const nowObj = new Date();
  const currentHour = customHour !== null ? customHour : nowObj.getHours();
  const nowStr = customTime || formatTime(nowObj);

  todayRecord.clockOut = nowStr;

  // Early logoff rule: logoff before 5:00 PM (17:00) -> EARLY_LOGOFF (Yellow)
  if (currentHour < 17) {
    todayRecord.status = ATTENDANCE_STATUS.EARLY_LOGOFF;
  } else {
    todayRecord.status = ATTENDANCE_STATUS.PRESENT;
  }

  store[userId] = userRecords;
  setStorage(store);
  return todayRecord;
}

export function getMonthDays(userId, year, month) {
  const store = getStorage();
  const userRecords = store[userId] || [];
  const recordMap = {};
  userRecords.forEach((r) => {
    recordMap[r.date] = r;
  });

  const firstDayOfWeek = new Date(year, month, 1).getDay(); // 0 = Sun, ..., 6 = Sat
  const totalDays = new Date(year, month + 1, 0).getDate();
  const todayStr = getTodayDateString();
  const days = [];

  // Add leading empty offset cells so Day 1 aligns precisely under its actual weekday column
  for (let i = 0; i < firstDayOfWeek; i++) {
    days.push({
      date: `empty-${i}`,
      isEmpty: true,
    });
  }

  for (let d = 1; d <= totalDays; d++) {
    const dateObj = new Date(year, month, d);
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const dayNumStr = String(d).padStart(2, '0');
    const dayStr = `${y}-${m}-${dayNumStr}`;
    const dayOfWeek = dateObj.getDay(); // 0 = Sun, 6 = Sat
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

    const existingRecord = recordMap[dayStr];
    if (existingRecord) {
      days.push({
        date: dayStr,
        dayNumber: d,
        isWeekend,
        isEmpty: false,
        clockIn: existingRecord.clockIn,
        clockOut: existingRecord.clockOut,
        status: existingRecord.status,
      });
    } else {
      const isPast = dayStr < todayStr;
      const defaultStatus = isWeekend ? 'WEEKEND' : isPast ? ATTENDANCE_STATUS.ABSENT : 'UPCOMING';
      days.push({
        date: dayStr,
        dayNumber: d,
        isWeekend,
        isEmpty: false,
        clockIn: null,
        clockOut: null,
        status: defaultStatus,
      });
    }
  }

  return days;
}
