#include <stdint.h>
#include <stdio.h>

#include <gst/gst.h>
#include <gst/base/gstbasetransform.h>


/* =========================================================
 * Demura NEON Function
 * ========================================================= */

void demura_process_neon(
    uint8_t *frame,
    const uint16_t *gain,
    int frame_w,
    int x_min,
    int y_min,
    int x_max,
    int y_max
);


/* =========================================================
 * Runtime Frame Configuration
 * ========================================================= */

#define FRAME_W 640
#define FRAME_H 480
#define FRAME_CHANNELS 3
#define FRAME_SIZE (FRAME_W * FRAME_H * FRAME_CHANNELS)


/* =========================================================
 * Plugin Definition
 * ========================================================= */

#ifndef PACKAGE
#define PACKAGE "demura"
#endif


#define GST_TYPE_DEMURA_TRANSFORM \
    (gst_demura_transform_get_type())


G_DECLARE_FINAL_TYPE(
    GstDemuraTransform,
    gst_demura_transform,
    GST,
    DEMURA_TRANSFORM,
    GstBaseTransform
)


struct _GstDemuraTransform
{
    GstBaseTransform parent;

    /* Runtime Control */
    gboolean enabled;

    /* ROI */
    gint x_min;
    gint y_min;
    gint x_max;
    gint y_max;

    /* Gain */
    gchar *gain_file;
    uint16_t *gain_q8;

    gsize gain_count;
    gboolean gain_loaded;
};


G_DEFINE_TYPE(
    GstDemuraTransform,
    gst_demura_transform,
    GST_TYPE_BASE_TRANSFORM
)


/* =========================================================
 * Properties
 * ========================================================= */

enum
{
    PROP_0,

    PROP_ENABLED,

    PROP_X_MIN,
    PROP_Y_MIN,
    PROP_X_MAX,
    PROP_Y_MAX,

    PROP_GAIN_FILE
};


/* =========================================================
 * Input / Output Caps
 *
 * Demura Runtime:
 *     BGR
 *     640 x 480
 * ========================================================= */

static GstStaticPadTemplate sink_template =
GST_STATIC_PAD_TEMPLATE(
    "sink",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS(
        "video/x-raw, "
        "format=(string)BGR, "
        "width=(int)640, "
        "height=(int)480"
    )
);


static GstStaticPadTemplate src_template =
GST_STATIC_PAD_TEMPLATE(
    "src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS(
        "video/x-raw, "
        "format=(string)BGR, "
        "width=(int)640, "
        "height=(int)480"
    )
);


/* =========================================================
 * Release Gain
 * ========================================================= */

static void
gst_demura_transform_release_gain(
    GstDemuraTransform *self
)
{
    if (self->gain_q8 != NULL)
    {
        g_free(self->gain_q8);

        self->gain_q8 = NULL;
    }

    self->gain_count = 0;
    self->gain_loaded = FALSE;
}


/* =========================================================
 * Load Q8 Gain
 * ========================================================= */

static gboolean
gst_demura_transform_load_gain(
    GstDemuraTransform *self
)
{
    FILE *fp;

    long file_size;

    gsize roi_w;
    gsize roi_h;

    gsize expected_count;
    gsize expected_bytes;

    size_t read_count;


    /* -----------------------------------------------------
     * Validate ROI
     * ----------------------------------------------------- */

    if (self->x_min < 0 ||
        self->y_min < 0 ||
        self->x_max > FRAME_W ||
        self->y_max > FRAME_H ||
        self->x_max <= self->x_min ||
        self->y_max <= self->y_min)
    {
        g_printerr(
            "[Demura Transform] Invalid ROI: "
            "x=%d~%d y=%d~%d\n",
            self->x_min,
            self->x_max,
            self->y_min,
            self->y_max
        );

        return FALSE;
    }


    /* -----------------------------------------------------
     * Validate Gain File
     * ----------------------------------------------------- */

    if (self->gain_file == NULL ||
        self->gain_file[0] == '\0')
    {
        g_printerr(
            "[Demura Transform] "
            "Gain file is not configured\n"
        );

        return FALSE;
    }


    /* -----------------------------------------------------
     * Calculate Expected Gain Size
     * ----------------------------------------------------- */

    roi_w =
        (gsize)(self->x_max - self->x_min);

    roi_h =
        (gsize)(self->y_max - self->y_min);


    expected_count =
        roi_w *
        roi_h *
        FRAME_CHANNELS;


    expected_bytes =
        expected_count *
        sizeof(uint16_t);


    g_print(
        "[Demura Transform] Loading Gain\n"
    );


    g_print(
        "[Demura Transform] Gain File : %s\n",
        self->gain_file
    );


    g_print(
        "[Demura Transform] ROI       : "
        "x=%d~%d y=%d~%d\n",
        self->x_min,
        self->x_max,
        self->y_min,
        self->y_max
    );


    g_print(
        "[Demura Transform] Work Size : "
        "%zu x %zu\n",
        roi_w,
        roi_h
    );


    g_print(
        "[Demura Transform] Expected  : "
        "%zu values / %zu bytes\n",
        expected_count,
        expected_bytes
    );


    /* -----------------------------------------------------
     * Open Gain File
     * ----------------------------------------------------- */

    fp = fopen(
        self->gain_file,
        "rb"
    );


    if (fp == NULL)
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to open Gain file: %s\n",
            self->gain_file
        );

        return FALSE;
    }


    /* -----------------------------------------------------
     * Check Actual File Size
     * ----------------------------------------------------- */

    if (fseek(fp, 0, SEEK_END) != 0)
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to seek Gain file\n"
        );

        fclose(fp);

        return FALSE;
    }


    file_size = ftell(fp);


    if (file_size < 0)
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to get Gain file size\n"
        );

        fclose(fp);

        return FALSE;
    }


    rewind(fp);


    if ((gsize)file_size != expected_bytes)
    {
        g_printerr(
            "[Demura Transform] "
            "Gain file size mismatch\n"
        );

        g_printerr(
            "[Demura Transform] "
            "Expected=%zu bytes Actual=%ld bytes\n",
            expected_bytes,
            file_size
        );

        fclose(fp);

        return FALSE;
    }


    /* -----------------------------------------------------
     * Release Previous Gain
     * ----------------------------------------------------- */

    gst_demura_transform_release_gain(
        self
    );


    /* -----------------------------------------------------
     * Allocate Gain Memory
     * ----------------------------------------------------- */

    self->gain_q8 =
        g_malloc(expected_bytes);


    if (self->gain_q8 == NULL)
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to allocate Gain memory\n"
        );

        fclose(fp);

        return FALSE;
    }


    /* -----------------------------------------------------
     * Read Gain
     * ----------------------------------------------------- */

    read_count =
        fread(
            self->gain_q8,
            sizeof(uint16_t),
            expected_count,
            fp
        );


    fclose(fp);


    if (read_count != expected_count)
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to read complete Gain data\n"
        );

        g_printerr(
            "[Demura Transform] "
            "Expected=%zu Read=%zu\n",
            expected_count,
            read_count
        );


        gst_demura_transform_release_gain(
            self
        );


        return FALSE;
    }


    self->gain_count =
        expected_count;


    self->gain_loaded =
        TRUE;


    g_print(
        "[Demura Transform] "
        "Gain loaded successfully\n"
    );


    return TRUE;
}


/* =========================================================
 * Set Property
 * ========================================================= */

static void
gst_demura_transform_set_property(
    GObject *object,
    guint property_id,
    const GValue *value,
    GParamSpec *pspec
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(object);


    switch (property_id)
    {
        case PROP_ENABLED:

            self->enabled =
                g_value_get_boolean(value);

            g_print(
                "[Demura Transform] Enabled = %s\n",
                self->enabled ? "TRUE" : "FALSE"
            );

            break;


        case PROP_X_MIN:

            self->x_min =
                g_value_get_int(value);

            break;


        case PROP_Y_MIN:

            self->y_min =
                g_value_get_int(value);

            break;


        case PROP_X_MAX:

            self->x_max =
                g_value_get_int(value);

            break;


        case PROP_Y_MAX:

            self->y_max =
                g_value_get_int(value);

            break;


        case PROP_GAIN_FILE:

            g_free(
                self->gain_file
            );


            self->gain_file =
                g_value_dup_string(value);

            break;


        default:

            G_OBJECT_WARN_INVALID_PROPERTY_ID(
                object,
                property_id,
                pspec
            );

            break;
    }
}


/* =========================================================
 * Get Property
 * ========================================================= */

static void
gst_demura_transform_get_property(
    GObject *object,
    guint property_id,
    GValue *value,
    GParamSpec *pspec
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(object);


    switch (property_id)
    {
        case PROP_ENABLED:

            g_value_set_boolean(
                value,
                self->enabled
            );

            break;


        case PROP_X_MIN:

            g_value_set_int(
                value,
                self->x_min
            );

            break;


        case PROP_Y_MIN:

            g_value_set_int(
                value,
                self->y_min
            );

            break;


        case PROP_X_MAX:

            g_value_set_int(
                value,
                self->x_max
            );

            break;


        case PROP_Y_MAX:

            g_value_set_int(
                value,
                self->y_max
            );

            break;


        case PROP_GAIN_FILE:

            g_value_set_string(
                value,
                self->gain_file
            );

            break;


        default:

            G_OBJECT_WARN_INVALID_PROPERTY_ID(
                object,
                property_id,
                pspec
            );

            break;
    }
}


/* =========================================================
 * Frame Processing
 * ========================================================= */

static GstFlowReturn
gst_demura_transform_transform_ip(
    GstBaseTransform *base,
    GstBuffer *buffer
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(base);


    static guint64 frame_count = 0;


    GstMapInfo map;


    frame_count++;


    /* -----------------------------------------------------
     * Demura OFF -> Pass Through
     * ----------------------------------------------------- */

    if (!self->enabled)
    {
        return GST_FLOW_OK;
    }


    /* -----------------------------------------------------
     * Gain Not Ready -> Pass Through
     * ----------------------------------------------------- */

    if (!self->gain_loaded ||
        self->gain_q8 == NULL)
    {
        return GST_FLOW_OK;
    }


    /* -----------------------------------------------------
     * Writable Streaming Frame
     * ----------------------------------------------------- */

    if (!gst_buffer_map(
            buffer,
            &map,
            GST_MAP_READWRITE))
    {
        g_printerr(
            "[Demura Transform] "
            "Failed to map buffer\n"
        );

        return GST_FLOW_ERROR;
    }


    /* -----------------------------------------------------
     * Frame Size Check
     * ----------------------------------------------------- */

    if (map.size < FRAME_SIZE)
    {
        g_printerr(
            "[Demura Transform] "
            "Invalid frame size: %zu "
            "(expected >= %d)\n",
            map.size,
            FRAME_SIZE
        );


        gst_buffer_unmap(
            buffer,
            &map
        );


        return GST_FLOW_ERROR;
    }


    /* -----------------------------------------------------
     * NEON Demura
     * ----------------------------------------------------- */

    demura_process_neon(
        map.data,
        self->gain_q8,
        FRAME_W,
        self->x_min,
        self->y_min,
        self->x_max,
        self->y_max
    );


    /* -----------------------------------------------------
     * Debug
     * ----------------------------------------------------- */

    if (frame_count % 30 == 0)
    {
        g_print(
            "[Demura Transform] "
            "NEON Frame=%" G_GUINT64_FORMAT
            " Size=%zu "
            "ROI=(%d,%d)-(%d,%d)\n",
            frame_count,
            map.size,
            self->x_min,
            self->y_min,
            self->x_max,
            self->y_max
        );
    }


    gst_buffer_unmap(
        buffer,
        &map
    );


    return GST_FLOW_OK;
}


/* =========================================================
 * Start
 * ========================================================= */

static gboolean
gst_demura_transform_start(
    GstBaseTransform *base
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(base);


    g_print(
        "[Demura Transform] Start\n"
    );


    /*
     * Demura OFF:
     * no need to load Gain.
     */

    if (!self->enabled)
    {
        g_print(
            "[Demura Transform] "
            "Disabled -> Pass Through\n"
        );

        return TRUE;
    }


    /*
     * Demura ON:
     * load Gain once.
     */

    if (!gst_demura_transform_load_gain(
            self))
    {
        g_printerr(
            "[Demura Transform] "
            "Gain load failed -> Pass Through\n"
        );


        self->gain_loaded =
            FALSE;


        /*
         * Do not break entire GStreamer Pipeline.
         */

        return TRUE;
    }


    g_print(
        "[Demura Transform] Ready\n"
    );


    return TRUE;
}


/* =========================================================
 * Stop
 * ========================================================= */

static gboolean
gst_demura_transform_stop(
    GstBaseTransform *base
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(base);


    g_print(
        "[Demura Transform] Stop\n"
    );


    gst_demura_transform_release_gain(
        self
    );


    return TRUE;
}


/* =========================================================
 * Finalize
 * ========================================================= */

static void
gst_demura_transform_finalize(
    GObject *object
)
{
    GstDemuraTransform *self =
        GST_DEMURA_TRANSFORM(object);


    gst_demura_transform_release_gain(
        self
    );


    g_free(
        self->gain_file
    );


    self->gain_file =
        NULL;


    G_OBJECT_CLASS(
        gst_demura_transform_parent_class
    )->finalize(
        object
    );
}


/* =========================================================
 * Class Initialize
 * ========================================================= */

static void
gst_demura_transform_class_init(
    GstDemuraTransformClass *klass
)
{
    GObjectClass *gobject_class =
        G_OBJECT_CLASS(klass);


    GstElementClass *element_class =
        GST_ELEMENT_CLASS(klass);


    GstBaseTransformClass *transform_class =
        GST_BASE_TRANSFORM_CLASS(klass);


    /* -----------------------------------------------------
     * GObject
     * ----------------------------------------------------- */

    gobject_class->set_property =
        gst_demura_transform_set_property;


    gobject_class->get_property =
        gst_demura_transform_get_property;


    gobject_class->finalize =
        gst_demura_transform_finalize;


    /* -----------------------------------------------------
     * Properties
     * ----------------------------------------------------- */

    g_object_class_install_property(
        gobject_class,
        PROP_ENABLED,
        g_param_spec_boolean(
            "enabled",
            "Enabled",
            "Enable Demura processing",
            FALSE,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    g_object_class_install_property(
        gobject_class,
        PROP_X_MIN,
        g_param_spec_int(
            "x-min",
            "X Min",
            "Demura ROI minimum X",
            0,
            FRAME_W,
            0,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    g_object_class_install_property(
        gobject_class,
        PROP_Y_MIN,
        g_param_spec_int(
            "y-min",
            "Y Min",
            "Demura ROI minimum Y",
            0,
            FRAME_H,
            0,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    g_object_class_install_property(
        gobject_class,
        PROP_X_MAX,
        g_param_spec_int(
            "x-max",
            "X Max",
            "Demura ROI maximum X",
            0,
            FRAME_W,
            FRAME_W,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    g_object_class_install_property(
        gobject_class,
        PROP_Y_MAX,
        g_param_spec_int(
            "y-max",
            "Y Max",
            "Demura ROI maximum Y",
            0,
            FRAME_H,
            FRAME_H,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    g_object_class_install_property(
        gobject_class,
        PROP_GAIN_FILE,
        g_param_spec_string(
            "gain-file",
            "Gain File",
            "Path to Demura Q8 Gain binary file",
            NULL,
            G_PARAM_READWRITE |
            G_PARAM_STATIC_STRINGS
        )
    );


    /* -----------------------------------------------------
     * Metadata
     * ----------------------------------------------------- */

    gst_element_class_set_static_metadata(
        element_class,
        "Demura Transform",
        "Filter/Effect/Video",
        "Demura NEON processing transform",
        "AR Glasses Demo"
    );


    /* -----------------------------------------------------
     * Pads
     * ----------------------------------------------------- */

    gst_element_class_add_static_pad_template(
        element_class,
        &sink_template
    );


    gst_element_class_add_static_pad_template(
        element_class,
        &src_template
    );


    /* -----------------------------------------------------
     * GstBaseTransform
     * ----------------------------------------------------- */

    transform_class->start =
        GST_DEBUG_FUNCPTR(
            gst_demura_transform_start
        );


    transform_class->stop =
        GST_DEBUG_FUNCPTR(
            gst_demura_transform_stop
        );


    transform_class->transform_ip =
        GST_DEBUG_FUNCPTR(
            gst_demura_transform_transform_ip
        );
}


/* =========================================================
 * Instance Initialize
 * ========================================================= */

static void
gst_demura_transform_init(
    GstDemuraTransform *self
)
{
    gst_base_transform_set_in_place(
        GST_BASE_TRANSFORM(self),
        TRUE
    );


    /* Default State */

    self->enabled =
        FALSE;


    self->x_min =
        0;


    self->y_min =
        0;


    self->x_max =
        FRAME_W;


    self->y_max =
        FRAME_H;


    self->gain_file =
        NULL;


    self->gain_q8 =
        NULL;


    self->gain_count =
        0;


    self->gain_loaded =
        FALSE;
}


/* =========================================================
 * Plugin Register
 * ========================================================= */

static gboolean
plugin_init(
    GstPlugin *plugin
)
{
    return gst_element_register(
        plugin,
        "demuratransform",
        GST_RANK_NONE,
        GST_TYPE_DEMURA_TRANSFORM
    );
}


/* =========================================================
 * Plugin Definition
 * ========================================================= */

GST_PLUGIN_DEFINE(
    GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    demura,
    "Demura GStreamer Plugin",
    plugin_init,
    "1.0",
    "LGPL",
    "Demura",
    "AR Glasses Demo"
)