//node bunnyFFVideos.js

//read API keys
const fs = require('fs')
const { bunny: { ACCESS_KEY, TOKEN_KEY } } = JSON.parse(fs.readFileSync('./SUPERMINISTREAM_AUTH_FILE.json', 'utf8'))
const EXPIRES = "1730433600" //Nov 1, 2024

/**
 * This function generates a url with a token given a full file path
 * based on https://support.bunny.net/hc/en-us/articles/360016055099-How-to-sign-URLs-for-BunnyCDN-Token-Authentication
 * @param {string} path ex /vis24/a-ldav/a-ldav-1003/a-ldav-1003_Preview.mp4
 * @returns             url with token, ex https://ieeevis-uploads.b-cdn.net/vis24/a-ldav/a-ldav-1003/a-ldav-1003_Preview.mp4?token=PYJw_loXL4L1qAH_hlEUHMBLIR9img4Wuf2hw1VfGqw&expires=1730433600
 */
function generateUrlWithToken(path) {
  const { createHash } = require('crypto')
  const hashableBase = `${TOKEN_KEY}${path}${EXPIRES}`
  const base64Token = createHash('sha256').update(hashableBase).digest('base64').replaceAll("=","").replaceAll("\n","").replaceAll("+","-").replaceAll("/","_")
  
  const url = `https://ieeevis-uploads.b-cdn.net${path}?${new URLSearchParams({
    token: base64Token,
    expires: EXPIRES,
  })}`

  console.log("url",url)

  return url
}

/**
 * fetches the objects in bunny from a path
 * @param {string} path ex /vis24/a-ldav/a-ldav-1003/
 * @returns             the objects in that path in bunny as an array of objects, like this:
 * [{
    Guid: '8f7f3e8b-5106-49a3-bf09-198f6c372dd3',
    StorageZoneName: 'ieeevis-uploads',
    Path: '/ieeevis-uploads/vis24/',
    ObjectName: 'a-ldav',
    Length: 0,
    LastChanged: '2024-08-26T06:19:47.303',
    ServerId: 0,
    ArrayNumber: 0,
    IsDirectory: true,
    UserId: 'fdf6a130-5dc1-4097-9367-3fe586ff6b36',
    ContentType: '',
    DateCreated: '2024-08-26T06:19:47.303',
    StorageZoneId: 280918,
    Checksum: null,
    ReplicatedZones: null
  }]
 */
async function fetchObjectsFromPath(path) {
  return await fetch(path,{
    headers: {
      AccessKey: ACCESS_KEY
    }
  }).then(r => r.json())
}

/**
 * recursively find all the files in bunny, and call the file handler
 * @param {string} path 
 * @param {key-value object} dict 
 */
async function findAllFiles(path, dict) {
  const objects = await fetchObjectsFromPath(path)

  for(const obj of objects) {
    if(obj.IsDirectory) { //if this is a directory, 
      const url = "https://storage.bunnycdn.com" + obj.Path + obj.ObjectName + "/"
      await findAllFiles(url, dict)
    }
    else {
      handleFile(obj, dict)
    }
  }
}

/**
 * bunny object handler
 * generates the URLs for mp4 and srt files
 * @param {object from bunny} obj 
 * @param {key-value object} dict 
 */
function handleFile(obj, dict) {
  const isMp4 = obj.ObjectName.includes("_Preview.mp4")
  const isSrt = obj.ObjectName.includes("_Preview.srt")
  const uid = obj.ObjectName.split("_")[0]
  if(!dict[uid]) {
    dict[uid] = {
      uid,
      mp4: "",
      srt: "",
    }
  }

  if(isMp4 || isSrt) {
    const uid = obj.ObjectName.split("_")[0]
    const url = generateUrlWithToken(obj.Path.replaceAll("ieeevis-uploads/","") + obj.ObjectName)

    if(isMp4) {
      dict[uid].mp4 = url
    }
    else if(isSrt) {
      dict[uid].srt = url
    }
  }
}

/**
 * Main function that gets the preview video and subtitle URLs for 2024 data
 */
async function run() {
  //get all the URLs
  const dict = {}
  await findAllFiles("https://storage.bunnycdn.com/ieeevis-uploads/vis24/", dict)

  //write as CSV file
  const csvFileContent = `UID,FF Video Bunny URL,FF Video Subtitles Bunny URL\n` + (
    Object.values(dict).map(({uid,mp4,srt}) => {
      return `${uid},${mp4},${srt}`
    }).sort().join("\n")
  )
  fs.writeFileSync('./bunny-ff-videos.csv',csvFileContent)
}
run()


