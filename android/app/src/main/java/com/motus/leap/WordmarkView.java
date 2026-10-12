package com.motus.leap;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.view.View;

/** Fit the visible font glyphs, including their overhang, rather than just text advances. */
final class WordmarkView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float maxSize;
    WordmarkView(Context context, int sizeSp) {
        super(context); maxSize = sizeSp * getResources().getDisplayMetrics().scaledDensity;
        paint.setTypeface(Typeface.createFromAsset(context.getAssets(), "Deltha.otf")); paint.setColor(0xFFF3F5F8);
        setContentDescription("motus.leap");
    }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas); String text = "motus.leap";
        paint.setTextSize(maxSize); Rect bounds = new Rect(); paint.getTextBounds(text, 0, text.length(), bounds);
        float width = Math.max(paint.measureText(text), bounds.right) - Math.min(0, bounds.left);
        float scale = Math.min(1f, Math.min((getWidth()-16f)/width, (getHeight()-8f)/bounds.height()));
        paint.setTextSize(maxSize * Math.max(0.1f, scale)); paint.getTextBounds(text, 0, text.length(), bounds);
        canvas.drawText(text, (getWidth()-bounds.width())/2f-bounds.left, (getHeight()-bounds.height())/2f-bounds.top, paint);
    }
}
