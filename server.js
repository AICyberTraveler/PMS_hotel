const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');

const serviceAccount = require('./serviceAccountKey.json');
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});
const db = admin.firestore();

const app = express();
app.use(cors());
app.use(express.json());

// Guest checkout endpoint
app.post('/checkout', async (req, res) => {
  const { roomNumber } = req.body;
  const checkoutTime = new Date();

  // Update Firestore
  await db.collection('rooms').doc(roomNumber.toString()).set({
    checkedOut: true,
    checkoutTime
  }, { merge: true });

  // Optionally, send a notification (pseudo-code)
  // await sendNotificationToStaff(roomNumber);

  res.json({ success: true, message: `Room ${roomNumber} checked out.` });
});

// Get rooms needing cleaning
app.get('/rooms', async (req, res) => {
  const snapshot = await db.collection('rooms').where('checkedOut', '==', true).get();
  const rooms = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  res.json(rooms);
});

app.listen(4000, () => console.log('Server running on port 4000'));
