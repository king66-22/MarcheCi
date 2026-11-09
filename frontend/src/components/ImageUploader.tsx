import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { catalogueApi } from '../api/service'
import type { ProductImage } from '../api/types'
import { ErrorBanner, errMessage, useConfirm } from './ui'

const MAX_BYTES = 8 * 1024 * 1024
const ACCEPT = 'image/jpeg,image/png,image/webp'
const DEFAULT_MAX = 10

function fileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function GalleryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="8.5" cy="10" r="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="m4 17 5-5 4 4 3-3 4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CameraIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 8h3l1.5-2h7L17 8h3v11H4V8Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <circle cx="12" cy="13" r="3.2" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 7h16M9 7V5h6v2m-8 0 1 13h8l1-13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export interface ImageUploaderProps {
  /** null tant que le produit n'existe pas : les fichiers restent en attente. */
  productId: number | null
  images: ProductImage[]
  coverUrl: string | null
  pending: File[]
  onPendingChange: (files: File[]) => void
  onUploaded: (image: ProductImage) => void
  onDeleted: (imageId: number) => void
  onCover: (image: ProductImage) => void
  max?: number
  disabled?: boolean
}

export function ImageUploader({
  productId,
  images,
  coverUrl,
  pending,
  onPendingChange,
  onUploaded,
  onDeleted,
  onCover,
  max = DEFAULT_MAX,
  disabled = false,
}: ImageUploaderProps) {
  const galleryRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const cameraCancelledRef = useRef(false)
  const confirm = useConfirm()

  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(0)
  const [activeUpload, setActiveUpload] = useState<{ name: string; percent: number } | null>(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)

  // Aperçus locaux des fichiers pas encore envoyés (création de produit).
  const previews = useMemo(
    () => pending.map((file) => ({ file, key: fileKey(file), url: URL.createObjectURL(file) })),
    [pending],
  )

  // Libère les URL d'aperçu quand la liste change ou que le composant est démonté.
  useEffect(
    () => () => previews.forEach((preview) => URL.revokeObjectURL(preview.url)),
    [previews],
  )

  const total = images.length + pending.length
  const full = total >= max

  const upload = useCallback(async (files: File[]) => {
    if (productId === null || files.length === 0) return
    setError(null)
    for (const file of files) {
      setUploading((count) => count + 1)
      setActiveUpload({ name: file.name, percent: 0 })
      try {
        const { data } = await catalogueApi.uploadProductImage(productId, file, (percent) => {
          setActiveUpload({ name: file.name, percent })
        })
        onUploaded(data)
      } catch (e) {
        setError(errMessage(e, `Envoi de « ${file.name} » impossible.`))
      } finally {
        setUploading((count) => Math.max(0, count - 1))
        setActiveUpload(null)
      }
    }
  }, [productId, onUploaded])

  const addFiles = useCallback(async (incoming: File[]) => {
    setError(null)
    const room = max - total - uploading
    if (room <= 0) {
      setError(`Maximum ${max} photos par produit. Supprimez une photo pour en ajouter une autre.`)
      return
    }

    const accepted: File[] = []
    for (const file of incoming) {
      if (!file.type.startsWith('image/')) {
        setError(`« ${file.name} » n'est pas une image.`)
        continue
      }
      if (file.size > MAX_BYTES) {
        setError(`« ${file.name} » dépasse 8 Mo. Compressez-la ou choisissez une autre photo.`)
        continue
      }
      if (accepted.length >= room) {
        setError(`Maximum ${max} photos par produit.`)
        break
      }
      accepted.push(file)
    }
    if (accepted.length === 0) return

    if (productId === null) {
      onPendingChange([...pending, ...accepted])
    } else {
      await upload(accepted)
    }
  }, [max, total, uploading, productId, pending, onPendingChange, upload])

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files && files.length > 0) void addFiles(Array.from(files))
    event.target.value = ''
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    void addFiles(Array.from(event.dataTransfer.files))
  }

  // Caméra en direct (ordinateur / navigateur compatible). Sur mobile, le
  // bouton « Prendre une photo » ouvre directement l'application appareil photo.
  useEffect(() => {
    if (!cameraOpen) return
    cameraCancelledRef.current = false

    // Le navigateur sans caméra est signalé dès le clic (openCamera).
    if (!navigator.mediaDevices?.getUserMedia) return

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
      .then((stream) => {
        if (cameraCancelledRef.current) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          void videoRef.current.play().catch(() => undefined)
        }
      })
      .catch(() => {
        if (!cameraCancelledRef.current) {
          setCameraError('Accès à la caméra refusé ou indisponible. Sur mobile, utilisez « Prendre une photo ».')
        }
      })

    return () => {
      cameraCancelledRef.current = true
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }, [cameraOpen])

  const openCamera = () => {
    setCameraError(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("La caméra n'est pas disponible dans ce navigateur. Utilisez « Prendre une photo ».")
    }
    setCameraOpen(true)
  }

  const closeCamera = () => setCameraOpen(false)

  const capture = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const file = new File([blob], `photo-${Date.now()}.jpg`, { type: 'image/jpeg' })
        closeCamera()
        void addFiles([file])
      },
      'image/jpeg',
      0.9,
    )
  }

  const removeImage = (image: ProductImage) => {
    if (productId === null) return
    confirm('Supprimer cette photo du produit ?', () => {
      void catalogueApi
        .deleteProductImage(productId, image.id)
        .then(() => onDeleted(image.id))
        .catch((e) => setError(errMessage(e, 'Suppression de la photo impossible.')))
    })
  }

  const removePending = (key: string) => {
    onPendingChange(pending.filter((file) => fileKey(file) !== key))
  }

  const makeCover = (image: ProductImage) => {
    if (productId === null || image.url === coverUrl) return
    void catalogueApi
      .setProductCover(productId, image.id)
      .then(() => onCover(image))
      .catch((e) => setError(errMessage(e, 'Mise à jour de la couverture impossible.')))
  }

  return (
    <section className="rounded-2xl border border-sable-200 bg-sable-50/60 p-4" aria-labelledby="photos-titre">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="photos-titre" className="font-bold text-slate-800">Photos du produit</h3>
          <p className="text-xs text-slate-500">
            {total}/{max} photo{total > 1 ? 's' : ''} · la première sert de couverture
          </p>
        </div>
        {activeUpload && (
          <span className="text-xs font-semibold text-terracotta-700" role="status">
            Envoi de {activeUpload.name} · {activeUpload.percent} %
          </span>
        )}
      </div>

      <div
        className={`mt-3 rounded-xl border-2 border-dashed p-4 text-center transition ${
          dragging ? 'border-terracotta-500 bg-terracotta-50' : 'border-sable-200 bg-white'
        } ${disabled || full ? 'opacity-60' : ''}`}
        onDragOver={(event) => { event.preventDefault(); if (!disabled && !full) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <p className="text-sm font-semibold text-slate-700">Glissez-déposez vos photos ici</p>
        <p className="mt-1 text-xs text-slate-500">JPEG, PNG ou WebP · 8 Mo maximum par photo</p>

        <div className="mt-3 flex flex-wrap justify-center gap-2">
          <button
            type="button"
            className="button-secondary"
            disabled={disabled || full}
            onClick={() => galleryRef.current?.click()}
          >
            <GalleryIcon /> Choisir dans la galerie
          </button>
          <button
            type="button"
            className="button-primary"
            disabled={disabled || full}
            onClick={() => cameraRef.current?.click()}
          >
            <CameraIcon /> Prendre une photo
          </button>
          <button
            type="button"
            className="button-secondary"
            disabled={disabled || full}
            onClick={openCamera}
            title="Caméra en direct (ordinateur)"
          >
            <CameraIcon /> Caméra
          </button>
        </div>

        <input
          ref={galleryRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={onPick}
        />
        {/* capture="environment" : ouvre directement l'appareil photo arrière sur mobile */}
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={onPick}
        />
      </div>

      {productId === null && pending.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          Les photos seront envoyées automatiquement juste après la création du produit.
        </p>
      )}

      {(images.length > 0 || previews.length > 0) && (
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {images.map((image) => (
            <li key={image.id} className="overflow-hidden rounded-xl border border-sable-200 bg-white">
              <div className="relative">
                <img src={image.url} alt="Photo du produit" className="aspect-square w-full object-cover" />
                {image.url === coverUrl && (
                  <span className="absolute left-1.5 top-1.5 rounded-full bg-marche-800 px-2 py-0.5 text-[10px] font-bold text-white">
                    Couverture
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between gap-1 p-1.5">
                <button
                  type="button"
                  className="text-[11px] font-semibold text-terracotta-700 hover:underline disabled:opacity-40"
                  disabled={disabled || image.url === coverUrl}
                  onClick={() => makeCover(image)}
                >
                  Couverture
                </button>
                <button
                  type="button"
                  className="rounded p-1 text-red-600 hover:bg-red-50 disabled:opacity-40"
                  disabled={disabled}
                  onClick={() => removeImage(image)}
                  aria-label="Supprimer cette photo"
                  title="Supprimer"
                >
                  <TrashIcon />
                </button>
              </div>
            </li>
          ))}

          {previews.map(({ file, key, url }) => (
            <li key={key} className="overflow-hidden rounded-xl border border-dashed border-terracotta-300 bg-white">
              <div className="relative">
                <img src={url} alt={file.name} className="aspect-square w-full object-cover opacity-80" />
                <span className="absolute inset-x-0 bottom-0 bg-black/60 px-1.5 py-1 text-[10px] font-semibold text-white">
                  En attente d'envoi
                </span>
              </div>
              <div className="flex justify-end p-1.5">
                <button
                  type="button"
                  className="rounded p-1 text-red-600 hover:bg-red-50 disabled:opacity-40"
                  disabled={disabled}
                  onClick={() => removePending(key)}
                  aria-label={`Retirer ${file.name}`}
                  title="Retirer"
                >
                  <TrashIcon />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {error && <div className="mt-3"><ErrorBanner message={error} /></div>}

      {cameraOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Prendre une photo">
          <div className="w-full max-w-lg rounded-2xl bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-bold text-slate-800">Prendre une photo</h3>
              <button type="button" onClick={closeCamera} aria-label="Fermer la caméra" className="rounded-full px-2 text-xl leading-none text-slate-500 hover:bg-sable-100">×</button>
            </div>
            {cameraError ? (
              <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{cameraError}</p>
            ) : (
              <video ref={videoRef} playsInline muted className="mt-3 aspect-video w-full rounded-xl bg-black object-cover" />
            )}
            <div className="mt-4 flex gap-3">
              <button type="button" className="button-primary flex-1" onClick={capture} disabled={Boolean(cameraError)}>
                <CameraIcon /> Capturer
              </button>
              <button type="button" className="button-secondary" onClick={closeCamera}>Annuler</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
